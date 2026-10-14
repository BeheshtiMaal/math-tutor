"""Bounded SymPy providers. Production math runs only in a killable interpreter.

No sympify/parse_expr/LaTeX parser receives model text. The existing scalar AST
parser is the only input grammar; a small literal LaTeX normalizer serves steps.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import re
import sys
import threading
from pathlib import Path
from decimal import Decimal

from agent import Limits, parse_expression
from .ui_blocks import GraphParams, SampleResult, SamplingRequest, StepDataParams, StepParams


class ProviderFailure(ValueError):
    """Safe, fixed reason code; never includes input or provider exception text."""


_worker_slots = threading.BoundedSemaphore(4)


def parse_graph(expressions, parameters, limits):
    trees = [parse_expression(item.expression, limits) for item in expressions]
    def symbols(tree):
        return ({tree.value} if tree.op == "symbol" else set()).union(*(symbols(arg) for arg in tree.args))
    used = set().union(*(symbols(tree) for tree in trees)) - {"x"}
    if used != set(parameters):
        raise ProviderFailure("parameter_symbols")
    return trees


def step_syntax(value):
    """A bounded notation subset, not a general TeX interpreter."""
    value = value.strip().strip("$").replace("\\left", "").replace("\\right", "")
    value = value.replace("\\cdot", "*").replace("\\times", "*").replace("\\ln", "log")
    value = re.sub(r"\\log_\{([A-Za-z0-9.+-]+)\}\(([^(){}]+)\)", r"log(\2,\1)", value)
    value = re.sub(r"\\log_([A-Za-z0-9]+)\(([^(){}]+)\)", r"log(\2,\1)", value)
    value = value.replace("\\log", "log").replace("\\sin", "sin").replace("\\cos", "cos").replace("\\tan", "tan").replace("\\exp", "exp").replace("\\pi", "pi")
    # Nested braces are intentionally outside the supported normalization.
    value = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"((\1)/(\2))", value)
    value = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", value)
    value = re.sub(r"\^\{([^{}]+)\}", r"^(\1)", value)
    return value


def solution_set(value):
    """Recognize only a bounded, finite numeric set; never evaluate set text."""
    value = step_syntax(value).replace(r'\in', ' in ').replace(r'\{', '{').replace(r'\}', '}')
    number = r'[+-]?(?:[0-9]+(?:\.[0-9]+)?)'
    match = re.fullmatch(rf'([A-Za-z][A-Za-z0-9_]{{0,11}})\s+in\s*\{{\s*({number}(?:\s*,\s*{number}){{0,7}})\s*\}}', value)
    return (match[1], [part.strip() for part in match[2].split(',')]) if match else None


def parse_state(value, limits):
    normalized = step_syntax(value)
    if len(normalized) > 2048 or re.search(r"[<>`]|__|https?:|javascript:|[\x00-\x1f]", normalized, re.I):
        raise ProviderFailure("unsafe_state")
    finite_set = solution_set(value)
    if finite_set:
        variable, roots = finite_set
        # Its zero polynomial lets the existing solution-set comparison check
        # every root, including rejecting a lost second root.
        polynomial = '*'.join(f'({variable}-({root}))' for root in roots)
        return [parse_expression(polynomial, limits), parse_expression('0', limits)]
    # Recognized formal notation that the scalar grammar cannot express may be
    # shown as explicitly unsupported. Other malformed or code-like input drops.
    formal_function = re.search(r"(?<![A-Za-z0-9_])[A-Za-z]'*\s*\(", normalized)
    if "\\" in normalized or formal_function:
        commands = re.findall(r"\\([A-Za-z]+)", normalized)
        if (not commands and not formal_function) or any(cmd not in {"int", "sum", "lim", "infty", "to", "mathrm", "quad", "qquad", "frac", "sqrt", "prime"} for cmd in commands):
            raise ProviderFailure("unsafe_state")
        if not re.fullmatch(r"[A-Za-z0-9\\{}_+*/(),=.^'\s-]+", normalized):
            raise ProviderFailure("unsafe_state")
        return None
    if normalized.count("=") > 1:
        raise ProviderFailure("invalid_state")
    pieces = normalized.split("=")
    return [parse_expression(piece, limits) for piece in pieces]


def _builder(limits, parameters=None, scope=None, variable="x"):
    import sympy as sp
    from sympy.calculus.util import continuous_domain
    x = sp.Symbol(variable, real=True)
    parameters = parameters or {}
    scope = sp.S.Reals if scope is None else scope
    restrictions = []

    def build(node):
        if node.op == "number":
            value = Decimal(node.value)
            if len(value.as_tuple().digits) > limits.max_number_digits or abs(value.adjusted()) > limits.max_number_digits:
                raise ProviderFailure("number_limit")
            return sp.Rational(str(value))
        if node.op == "symbol":
            if node.value == variable:
                return x
            if node.value not in parameters:
                raise ProviderFailure("parameter_symbols")
            return sp.Rational(str(parameters[node.value]))
        if node.op == "constant":
            if node.value not in {"pi", "E"}:
                raise ProviderFailure("nonfinite_constant")
            return {"pi": sp.pi, "E": sp.E}[node.value]
        args = [build(arg) for arg in node.args]
        # Prevent huge finite-domain singularity enumerations before SymPy's
        # set operations. Periodic domain analysis supports bounded affine
        # arguments; nonlinear periodic arguments degrade to text instead.
        if node.op in {"sin", "cos", "tan"} and args[0].has(x):
            slope = sp.diff(args[0], x)
            if slope.has(x) or slope.is_number is not True or abs(slope) > 100:
                raise ProviderFailure("periodic_limit")
        if node.op == "add": result = sp.Add(*args, evaluate=False)
        elif node.op == "sub": result = sp.Add(args[0], sp.Mul(-1, args[1], evaluate=False), evaluate=False)
        elif node.op == "mul": result = sp.Mul(*args, evaluate=False)
        elif node.op == "neg": result = sp.Mul(-1, args[0], evaluate=False)
        elif node.op == "div":
            if sp.simplify(args[1]) == 0:
                raise ProviderFailure("division_zero")
            restrictions.append(scope - sp.solveset(args[1], x, domain=scope))
            result = sp.Mul(args[0], sp.Pow(args[1], -1, evaluate=False), evaluate=False)
        elif node.op == "pow":
            if node.args[1].op not in {"number", "symbol", "neg"} or (node.args[1].op == "neg" and node.args[1].args[0].op != "number"):
                raise ProviderFailure("power_limit")
            if args[1].is_number and (args[1].is_finite is not True or abs(args[1]) > limits.max_power_magnitude):
                raise ProviderFailure("power_limit")
            result = sp.Pow(*args, evaluate=False)
        elif node.op == "log" and len(args) == 2:
            base = args[1]
            if base.free_symbols or base.is_positive is not True or sp.simplify(base - 1) == 0:
                raise ProviderFailure("log_base")
            result = sp.Mul(sp.log(args[0], evaluate=False), sp.Pow(sp.log(base), -1, evaluate=False), evaluate=False)
        else:
            function = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "exp": sp.exp, "log": sp.log, "sqrt": sp.sqrt, "abs": sp.Abs}[node.op]
            result = function(args[0], evaluate=False)
        # Preserve domain restrictions of intermediates before cancellation.
        if node.op in {"log", "sqrt", "pow", "tan"}:
            restrictions.append(continuous_domain(result, x, scope))
        return result

    def domain(expressions):
        result = scope
        for expr in [*restrictions, *(continuous_domain(expr, x, scope) for expr in expressions)]:
            result = result.intersect(expr)
        if result.has(sp.ConditionSet):
            raise NotImplementedError()
        return result
    return x, build, domain


def _sample(payload, limits):
    import sympy as sp
    request = SamplingRequest.model_validate(payload)
    trees = parse_graph(request.expressions, request.parameters, limits)
    lo, hi = request.domain.min, request.domain.max
    interval = sp.Interval(sp.Rational(str(lo)), sp.Rational(str(hi)))
    series, highlights, warnings = [], [], []
    for index, (item, tree) in enumerate(zip(request.expressions, trees)):
        x, build, domain = _builder(limits, request.parameters, scope=interval)
        expression = build(tree)
        allowed = domain([expression]).intersect(interval)
        excluded = interval - allowed
        gaps = []
        parts = excluded.args if isinstance(excluded, sp.Union) else [excluded]
        for part in parts:
            if part is sp.S.EmptySet:
                continue
            if isinstance(part, sp.Interval):
                gaps.append({"from": float(part.start), "to": float(part.end), "reason": "undefined"})
            elif isinstance(part, sp.FiniteSet):
                gaps.extend({"from": float(point), "to": float(point), "reason": "discontinuity"} for point in part)
            else:
                raise ProviderFailure("unresolved_domain")
        # lambdify sees only an allowlisted AST built from SymPy constructors.
        evaluate = sp.lambdify(x, expression, modules="math", cse=False, docstring_limit=0)
        def value_at(value):
            if allowed.contains(sp.Rational(str(value))) is not sp.S.true:
                return None, "undefined"
            try:
                result = float(evaluate(value))
                if math.isfinite(result):
                    return result, None
            except (ValueError, OverflowError, ZeroDivisionError, TypeError):
                pass
            return None, "out_of_range"
        points = []
        for i in range(request.sample_count):
            value = lo + (hi - lo) * i / (request.sample_count - 1)
            y, reason = value_at(value)
            if y is not None:
                points.append({"x": value, "y": y})
            elif reason == "out_of_range":
                # Cover a grid cell so adjacent finite points cannot bridge it.
                half = (hi - lo) / (request.sample_count - 1) / 2
                gaps.append({"from": max(lo, value - half), "to": min(hi, value + half), "reason": reason})
        for highlight in request.highlight_points:
            y, _ = value_at(highlight.x)
            if y is None:
                warnings.append(f"highlight_undefined:{index}")
            else:
                highlights.append({"x": highlight.x, "y": y, "label": highlight.label, "series_index": index})
        series.append({"label": item.label, "points": points, "gaps": sorted(gaps, key=lambda gap: gap['from'])})
    return SampleResult(series=series, highlight_points=highlights, domain_warnings=list(dict.fromkeys(warnings))).model_dump(mode="json", by_alias=True)


def _steps(payload, limits):
    import sympy as sp
    params = StepParams.model_validate(payload)
    raw_states = [params.initial_expression, *(step.state for step in params.steps), params.final_expression]
    parsed = [parse_state(value, limits) for value in raw_states]
    def symbols(tree):
        return ({tree.value} if tree.op == "symbol" else set()).union(*(symbols(arg) for arg in tree.args))
    used = set().union(*(symbols(tree) for trees in parsed if trees for tree in trees))
    # A worked example may use z or t. Preserve that source variable instead of
    # silently renaming it to x; multivariate transformations remain unsupported.
    variable = next(iter(used)) if len(used) == 1 else "x"
    prepared = []
    for raw, trees in zip(raw_states, parsed):
        if trees is None:
            prepared.append((raw, None, None, None))
            continue
        if len(used) > 1:
            prepared.append((raw, None, None, None))
            continue
        x, build, domain = _builder(limits, variable=variable)
        expressions = [build(tree) for tree in trees]
        try:
            allowed = domain(expressions)
        except NotImplementedError:
            allowed = None
        latex = " = ".join(sp.latex(expr) for expr in expressions)
        finite_set = solution_set(raw)
        if finite_set:
            _, roots = finite_set
            values = [build(parse_expression(root, limits)) for root in roots]
            latex = sp.latex(x) + r' \in ' + sp.latex(sp.FiniteSet(*values))
        if len(latex) > 1024:
            raise ProviderFailure("render_limit")
        prepared.append((latex, expressions, allowed, x))

    def compare(a, b):
        if a[1] is None or b[1] is None:
            return "unsupported"
        if a[2] is None or b[2] is None:
            return "unknown"
        if len(a[1]) != len(b[1]):
            return "unsupported"
        if len(a[1]) == 2:
            first = sp.solveset(a[1][0] - a[1][1], a[3], domain=a[2])
            second = sp.solveset(b[1][0] - b[1][1], b[3], domain=b[2])
            if first.has(sp.ConditionSet) or second.has(sp.ConditionSet):
                return "unknown"
            difference = first.symmetric_difference(second)
            if difference is sp.S.EmptySet:
                return "verified"
            if difference.is_empty is False:
                raise ProviderFailure("false_transformation")
            return "unknown"
        difference = sp.simplify(a[1][0] - b[1][0])
        if difference == 0 and a[2] == b[2]:
            return "verified"
        if difference.is_zero is False or (a[2].symmetric_difference(b[2])).is_empty is False:
            raise ProviderFailure("false_transformation")
        return "unknown"

    # Envelope endpoints must match actual first and last rows, rather than
    # smuggling a different final answer next to checked transformations.
    if (parsed[0] != parsed[1] or parsed[-1] != parsed[-2]
            or (parsed[0] is None and step_syntax(raw_states[0]) != step_syntax(raw_states[1]))
            or (parsed[-1] is None and step_syntax(raw_states[-1]) != step_syntax(raw_states[-2]))):
        raise ProviderFailure("step_endpoints")
    steps = []
    for index, step in enumerate(params.steps):
        status = compare(prepared[index], prepared[index + 1])
        steps.append({**step.model_dump(), "state": prepared[index + 1][0], "verification": status})
    result = {**params.model_dump(), "initial_expression": prepared[0][0], "final_expression": prepared[-1][0], "steps": steps}
    return StepDataParams.model_validate(result).model_dump(mode="json")


async def run_provider(kind, payload, limits):
    """JSON IPC, bounded output, deadline, cancellation and child cleanup."""
    process = None
    if not _worker_slots.acquire(blocking=False):
        raise ProviderFailure("busy")
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "webapp.providers", stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            cwd=str(Path(__file__).resolve().parents[1]),
            creationflags=0x08000000 if os.name == "nt" else 0)
        envelope = json.dumps({"kind": kind, "payload": payload, "limits": limits.model_dump()}).encode()
        output, _ = await asyncio.wait_for(process.communicate(envelope), limits.math_timeout_seconds)
        if process.returncode or len(output) > 1_000_000:
            raise ProviderFailure("worker_failed")
        response = json.loads(output)
        if response.get("error"):
            raise ProviderFailure(response['error'])
        if kind == "sample":
            return SampleResult.model_validate(response['data'])
        return StepDataParams.model_validate(response['data'])
    except asyncio.TimeoutError:
        raise ProviderFailure("timeout") from None
    except (OSError, json.JSONDecodeError):
        raise ProviderFailure("worker_failed") from None
    finally:
        try:
            if process is not None and process.returncode is None:
                process.kill()
                await process.communicate()
        finally:
            _worker_slots.release()


async def sample_graph(request: SamplingRequest, limits: Limits):
    parse_graph(request.expressions, request.parameters, limits)
    return await run_provider("sample", request.model_dump(mode="json"), limits)


def _worker_entry():
    try:
        envelope = json.loads(sys.stdin.read(131073))
        limits = Limits.model_validate(envelope['limits'])
        operation = {"sample": _sample, "steps": _steps}[envelope['kind']]
        data = operation(envelope['payload'], limits)
        result = {"data": data}
    except ProviderFailure as exc:
        result = {"error": str(exc)}
    except Exception:
        result = {"error": "unsupported"}
    sys.stdout.write(json.dumps(result, ensure_ascii=True, allow_nan=False))


if __name__ == "__main__":
    _worker_entry()
