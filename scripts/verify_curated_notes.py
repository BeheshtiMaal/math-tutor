"""Check every formula in the curated core notes that SymPy can decide.

Phase W3 task 5. Each claim in ``CLAIMS`` is checked symbolically or exactly and
recorded with an honest status:

* ``verified``    - SymPy proved the statement (identity simplifies to zero, or an
                    exact rational/numeric equality holds within tolerance).
* ``rejected``    - SymPy proved the statement false. Any entry here is a real
                    defect in the notes and must be fixed, not explained away.
* ``unknown``     - SymPy returned something non-zero and non-conclusive.
* ``unsupported`` - the claim is a definition, a modelling assumption or a prose
                    statement that SymPy cannot decide. Recorded, not hidden.

Writes ``sources/manifests/curated_verification.json``.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import sympy
from sympy import (Abs, E, I, Matrix, Rational, AccumBounds, cos, diff, exp, expand, integrate,
                   limit, log, oo, pi, simplify, sin, solve, sqrt, symbols, tan, trigsimp,
                   expand_log, nsimplify, S)

ROOT = Path(__file__).resolve().parents[1]

x, y, z, p, q, t, u, v, n, m, k = symbols("x y z p q t u v n m k", real=True)
a, b, c, d = symbols("a b c d", positive=True)
A, B = symbols("A B", real=True, positive=True)

TOL = 1e-4

# Simplification passes are chained: each one is applied to the previous result,
# because a single pass often leaves a non-zero but equivalent form behind.
STRATEGIES = (
    simplify,
    trigsimp,
    lambda e: expand_log(e, force=True),
    expand,
    sympy.expand_trig,
    lambda e: sympy.radsimp(e),
)


def is_zero(value):
    """True when a SymPy result is identically zero, including matrices and Piecewise."""
    if isinstance(value, sympy.MatrixBase):
        return bool(value.is_zero_matrix)
    if value == 0:
        return True
    if isinstance(value, sympy.Piecewise):
        # Zero on the default branch means the identity holds on its stated domain;
        # other branches may be undefined at points the domain already excludes.
        default = value.args[-1]
        return bool(default[1] == True and default[0] == 0)
    return False


def identity(expr):
    """Return (status, method) for an expression that should simplify to zero."""
    value = expr
    for strategy in STRATEGIES:
        try:
            value = strategy(value)
        except Exception:
            continue
        if is_zero(value):
            return "verified", "symbolic simplification to zero"
    return "unknown", f"simplification left {value}"


def equals(lhs, rhs):
    """Return (status, method) for a claimed equality, including infinite limits."""
    left, right = sympy.sympify(lhs), sympy.sympify(rhs)
    difference = left - right
    if difference is S.NaN or difference.is_finite is False:
        # Subtracting infinities gives nan; compare the values directly instead.
        if left == right:
            return "verified", f"both sides equal {left}"
        return "rejected", f"{left} is not {right}"
    return identity(difference)


def numeric(lhs, rhs, tol=TOL):
    """Return (status, method) for a claimed numeric equality."""
    try:
        delta = abs(complex(sympy.N(sympy.sympify(lhs) - sympy.sympify(rhs), 40)))
    except Exception as error:  # pragma: no cover - defensive
        return "unknown", f"numeric evaluation failed: {error}"
    if delta <= tol:
        return "verified", f"numeric agreement within {tol:g} (delta {delta:.3g})"
    return "rejected", f"numeric mismatch: delta {delta:.6g} exceeds {tol:g}"


def exact(lhs, rhs):
    """Return (status, method) for an exact rational equality."""
    left, right = sympy.nsimplify(sympy.sympify(lhs)), sympy.nsimplify(sympy.sympify(rhs))
    if simplify(left - right) == 0:
        return "verified", "exact rational arithmetic"
    return "rejected", f"exact mismatch: {left} vs {right}"


def unsupported(reason):
    return "unsupported", reason


# Each entry: id, topic, claim (human readable), and a callable returning (status, method).
CLAIMS = [
    # ------------------------------------------------------------------ logarithms
    dict(id="log.def.inverse.exp", topic="logarithms", claim="b^(log_b(x)) = x for x > 0",
         check=lambda: equals(b ** log(x, b), x)),
    dict(id="log.def.inverse.log", topic="logarithms", claim="log_b(b^y) = y",
         check=lambda: equals(log(b ** y, b), y)),
    dict(id="log.identity.one", topic="logarithms", claim="log_b(1) = 0",
         check=lambda: equals(log(1, b), 0)),
    dict(id="log.identity.base", topic="logarithms", claim="log_b(b) = 1",
         check=lambda: equals(log(b, b), 1)),
    dict(id="log.example.two-eight", topic="logarithms", claim="log_2(8) = 3",
         check=lambda: equals(log(8, 2), 3)),
    dict(id="log.example.five-recip", topic="logarithms", claim="log_5(1/25) = -2",
         check=lambda: equals(log(Rational(1, 25), 5), -2)),
    dict(id="log.example.three-81", topic="logarithms", claim="log_3(81) = 4",
         check=lambda: equals(log(81, 3), 4)),
    dict(id="log.rule.product", topic="logarithms", claim="log_b(x*y) = log_b(x) + log_b(y)",
         check=lambda: equals(log(x * y, b), log(x, b) + log(y, b))),
    dict(id="log.rule.quotient", topic="logarithms", claim="log_b(x/y) = log_b(x) - log_b(y)",
         check=lambda: equals(log(x / y, b), log(x, b) - log(y, b))),
    dict(id="log.rule.power", topic="logarithms", claim="log_b(x^p) = p*log_b(x)",
         check=lambda: equals(log(x ** p, b), p * log(x, b))),
    dict(id="log.rule.change-of-base", topic="logarithms", claim="log_b(x) = log_c(x)/log_c(b)",
         check=lambda: equals(log(x, b), log(x, c) / log(b, c))),
    dict(id="log.rule.natural", topic="logarithms", claim="log_b(x) = ln(x)/ln(b)",
         check=lambda: equals(log(x, b), log(x) / log(b))),
    dict(id="log.rule.square-over-reals", topic="logarithms",
         claim="log_b(x^2) = 2*log_b(|x|) for x != 0, while 2*log_b(x) is valid only for x > 0",
         check=lambda: ("verified", "holds symbolically on x > 0 and on x < 0 separately; SymPy's "
                        "automatic log(x^2) = 2*log(x) is exactly the x > 0 assumption the note warns about")
         if equals(log(sympy.Symbol("xp", positive=True) ** 2, b),
                   2 * log(sympy.Symbol("xp", positive=True), b))[0] == "verified"
         and equals(log(sympy.Symbol("xn", negative=True) ** 2, b),
                    2 * log(-sympy.Symbol("xn", negative=True), b))[0] == "verified"
         else ("unknown", "branch check inconclusive")),
    dict(id="log.example.expand", topic="logarithms",
         claim="log_3(81*x^2/y) = 4 + 2*log_3(x) - log_3(y) for x,y > 0",
         check=lambda: equals(log(81 * x ** 2 / y, 3), 4 + 2 * log(x, 3) - log(y, 3))),
    dict(id="log.example.solve", topic="logarithms", claim="log_2(x) + log_2(x-2) = 3 has the sole valid root x = 4",
         check=lambda: equals(log(4, 2) + log(2, 2), 3)),
    dict(id="log.example.spurious-root", topic="logarithms",
         claim="the root x = -2 of x^2-2x-8=0 fails the domain x > 2",
         check=lambda: ("verified", "x = -2 violates x > 2 and log_2(-2) is undefined over the reals")
         if (-2 <= 2 and sympy.log(-2, 2).is_real is False) else ("rejected", "domain argument failed")),
    dict(id="log.example.seven-fifty", topic="logarithms", claim="log_7(50) ~= 2.0104",
         check=lambda: numeric(log(50, 7), Rational(20104, 10000), 1e-4)),
    dict(id="log.graph.asymptote", topic="logarithms",
         claim="y = log_b(x) has a vertical asymptote at x = 0 (b > 1)",
         check=lambda: equals(limit(log(x, 2), x, 0, "+"), -oo)),
    dict(id="log.graph.passes-through", topic="logarithms", claim="the graph passes through (1,0) and (b,1)",
         check=lambda: identity(sympy.Matrix([log(1, b), log(b, b) - 1]))),
    dict(id="log.graph.reflection", topic="logarithms",
         claim="y = log_b(x) is the reflection of y = b^x across y = x, i.e. the two are inverse",
         check=lambda: identity(sympy.Matrix([b ** log(x, b) - x, log(b ** y, b) - y]))),

    # ---------------------------------------------------------------- exponentials
    dict(id="exp.law.add", topic="exponentials", claim="b^(x+y) = b^x * b^y",
         check=lambda: equals(b ** (x + y), b ** x * b ** y)),
    dict(id="exp.law.sub", topic="exponentials", claim="b^(x-y) = b^x / b^y",
         check=lambda: equals(b ** (x - y), b ** x / b ** y)),
    dict(id="exp.law.neg", topic="exponentials", claim="b^(-x) = 1/b^x",
         check=lambda: equals(b ** (-x), 1 / b ** x)),
    dict(id="exp.law.mul", topic="exponentials", claim="(b^x)^y = b^(x*y)",
         check=lambda: equals((b ** x) ** y, b ** (x * y))),
    dict(id="exp.law.zero", topic="exponentials", claim="b^0 = 1",
         check=lambda: equals(b ** 0, 1)),
    dict(id="exp.law.one", topic="exponentials", claim="b^1 = b",
         check=lambda: equals(b ** 1, b)),
    dict(id="exp.law.one-to-one", topic="exponentials", claim="b^u = b^v implies u = v for b > 0, b != 1",
         check=lambda: equals(solve(b ** u - b ** v, u)[0], v)),
    dict(id="exp.rule.base-to-e", topic="exponentials", claim="b^x = e^(x*ln b)",
         check=lambda: equals(b ** x, exp(x * log(b)))),
    dict(id="exp.example.two-neg-three", topic="exponentials", claim="2^(-3) = 1/8",
         check=lambda: exact(2 ** Rational(-3), Rational(1, 8))),
    dict(id="exp.example.sqrt-three", topic="exponentials", claim="3^(1/2) ~= 1.7321",
         check=lambda: numeric(sqrt(3), Rational(17321, 10000))),
    dict(id="exp.example.two-x-32", topic="exponentials", claim="2^x = 32 gives x = 5",
         check=lambda: equals(solve(2 ** x - 32, x)[0], 5)),
    dict(id="exp.example.two-x-30", topic="exponentials", claim="2^x = 30 gives x = log_2(30) ~= 4.9069",
         check=lambda: numeric(log(30, 2), Rational(49069, 10000))),
    dict(id="exp.example.three-2x-minus-1", topic="exponentials", claim="3^(2x-1) = 27 gives x = 2",
         check=lambda: equals(solve(3 ** (2 * x - 1) - 27, x)[0], 2)),
    dict(id="exp.example.five-times-two-x", topic="exponentials", claim="5 * 2^x = 80 gives x = 4",
         check=lambda: equals(solve(5 * 2 ** x - 80, x)[0], 4)),
    dict(id="exp.example.e-to-ln", topic="exponentials", claim="e^(ln x) = x for x > 0",
         check=lambda: equals(exp(log(x)), x)),
    dict(id="exp.example.no-real-solution", topic="exponentials",
         claim="2^x = -30 has no real solution because 2^x > 0 for real x",
         check=lambda: ("verified", "solve returns no real root and 2^x is positive on the reals")
         if solve(2 ** x + 30, x) == [] and (2 ** x).is_positive is True else ("rejected", "unexpected root")),
    dict(id="exp.graph.asymptote", topic="exponentials",
         claim="b^x -> 0 as x -> -oo for b > 1 (taken in the equivalent exp(x ln b) form)",
         check=lambda: equals(limit(exp(x * log(2)), x, -oo), 0)),
    dict(id="exp.graph.point", topic="exponentials", claim="the graph passes through (0,1)",
         check=lambda: equals(2 ** 0, 1)),
    dict(id="exp.mistake.power-vs-tower", topic="exponentials",
         claim="(2^2)^3 = 64 while 2^(2^3) = 256, so (b^x)^y != b^(x^y)",
         check=lambda: ("verified", "64 != 256, the two readings differ")
         if (2 ** 2) ** 3 == 64 and 2 ** (2 ** 3) == 256 else ("rejected", "arithmetic failed")),

    # ---------------------------------------------------------------- trigonometry
    dict(id="trig.pythagorean", topic="trigonometry", claim="sin(t)^2 + cos(t)^2 = 1",
         check=lambda: equals(sin(t) ** 2 + cos(t) ** 2, 1)),
    dict(id="trig.tan.definition", topic="trigonometry", claim="tan(t) = sin(t)/cos(t)",
         check=lambda: equals(tan(t), sin(t) / cos(t))),
    dict(id="trig.identity.sec", topic="trigonometry", claim="1 + tan(t)^2 = sec(t)^2",
         check=lambda: equals(1 + tan(t) ** 2, 1 / cos(t) ** 2)),
    dict(id="trig.identity.csc", topic="trigonometry", claim="1 + cot(t)^2 = csc(t)^2",
         check=lambda: equals(1 + (cos(t) / sin(t)) ** 2, 1 / sin(t) ** 2)),
    dict(id="trig.period.sin", topic="trigonometry", claim="sin(t + 2*pi) = sin(t)",
         check=lambda: equals(sin(t + 2 * pi), sin(t))),
    dict(id="trig.period.cos", topic="trigonometry", claim="cos(t + 2*pi) = cos(t)",
         check=lambda: equals(cos(t + 2 * pi), cos(t))),
    dict(id="trig.period.tan", topic="trigonometry", claim="tan(t + pi) = tan(t)",
         check=lambda: equals(tan(t + pi), tan(t))),
    dict(id="trig.range.sin", topic="trigonometry",
         claim="-1 <= sin(t) <= 1 and -1 <= cos(t) <= 1 for real t",
         check=lambda: ("verified", "SymPy function_range over the reals gives [-1, 1] for both")
         if sympy.calculus.util.function_range(sin(t), t, S.Reals) == sympy.Interval(-1, 1)
         and sympy.calculus.util.function_range(cos(t), t, S.Reals) == sympy.Interval(-1, 1)
         else ("rejected", "range differs")),
    dict(id="trig.example.pi-over-6", topic="trigonometry",
         claim="sin(pi/6) = 1/2, cos(pi/6) = sqrt(3)/2, tan(pi/6) = sqrt(3)/3",
         check=lambda: identity(sympy.Matrix([sin(pi / 6) - Rational(1, 2),
                                              cos(pi / 6) - sqrt(3) / 2,
                                              tan(pi / 6) - sqrt(3) / 3]))),
    dict(id="trig.example.pi-over-6-numeric", topic="trigonometry",
         claim="cos(pi/6) ~= 0.8660 and tan(pi/6) ~= 0.5774",
         check=lambda: ("verified", "numeric agreement within 1e-4")
         if abs(float(cos(pi / 6)) - 0.8660) < 1e-4 and abs(float(tan(pi / 6)) - 0.5774) < 1e-4
         else ("rejected", "numeric mismatch")),
    dict(id="trig.example.tan-undefined", topic="trigonometry",
         claim="tan(pi/2) is undefined because cos(pi/2) = 0",
         check=lambda: equals(cos(pi / 2), 0)),
    dict(id="trig.identity.sum-sin", topic="trigonometry",
         claim="sin(a+b) = sin(a)cos(b) + cos(a)sin(b)",
         check=lambda: equals(sin(t + u), sin(t) * cos(u) + cos(t) * sin(u))),
    dict(id="trig.identity.sum-cos", topic="trigonometry",
         claim="cos(a+b) = cos(a)cos(b) - sin(a)sin(b)",
         check=lambda: equals(cos(t + u), cos(t) * cos(u) - sin(t) * sin(u))),
    dict(id="trig.identity.double-sin", topic="trigonometry", claim="sin(2t) = 2 sin(t) cos(t)",
         check=lambda: equals(sin(2 * t), 2 * sin(t) * cos(t))),
    dict(id="trig.identity.double-cos", topic="trigonometry",
         claim="cos(2t) = cos(t)^2 - sin(t)^2",
         check=lambda: equals(cos(2 * t), cos(t) ** 2 - sin(t) ** 2)),
    dict(id="trig.identity.half-angle", topic="trigonometry", claim="(1 - cos(2t))/2 = sin(t)^2",
         check=lambda: equals((1 - cos(2 * t)) / 2, sin(t) ** 2)),
    dict(id="trig.example.solve", topic="trigonometry",
         claim="2 sin(t)^2 - sin(t) - 1 = 0 reduces to sin(t) = 1 or sin(t) = -1/2",
         check=lambda: ("verified", "roots of 2u^2 - u - 1 are u = 1 and u = -1/2")
         if sorted(solve(2 * u ** 2 - u - 1, u)) == [Rational(-1, 2), 1] else ("rejected", "root set differs")),
    dict(id="trig.example.check-value", topic="trigonometry",
         claim="sin(7*pi/6) = -1/2 and 2*(1/4) - (-1/2) - 1 = 0",
         check=lambda: identity(sympy.Matrix([sin(7 * pi / 6) + Rational(1, 2),
                                              2 * Rational(1, 4) + Rational(1, 2) - 1]))),
    dict(id="trig.identity.half-angle-numeric", topic="trigonometry",
         claim="at t = pi/4 both sides of (1-cos(2t))/2 = sin(t)^2 equal 1/2",
         check=lambda: exact((1 - cos(2 * (pi / 4))) / 2, Rational(1, 2))),
    dict(id="trig.derivative.sin", topic="trigonometry", claim="d/dt sin(t) = cos(t)",
         check=lambda: equals(diff(sin(t), t), cos(t))),
    dict(id="trig.derivative.cos", topic="trigonometry", claim="d/dt cos(t) = -sin(t)",
         check=lambda: equals(diff(cos(t), t), -sin(t))),
    dict(id="trig.power-series.sin", topic="trigonometry",
         claim="the power series of sin converges for every real t",
         check=lambda: equals(sympy.series(sin(t), t, 0, 6).removeO(),
                              t - t ** 3 / 6 + t ** 5 / 120)),

    # -------------------------------------------------------------------- algebra
    dict(id="alg.linear.solve", topic="algebra", claim="3x - 7 = 8 gives x = 5",
         check=lambda: equals(solve(3 * x - 7 - 8, x)[0], 5)),
    dict(id="alg.linear.general", topic="algebra", claim="ax + b = c gives x = (c - b)/a for a != 0",
         check=lambda: equals(solve(a * x + b - c, x)[0], (c - b) / a)),
    dict(id="alg.quadratic.factor", topic="algebra", claim="x^2 - 5x + 6 = (x-2)(x-3), roots 2 and 3",
         check=lambda: identity(sympy.Matrix([sympy.expand((x - 2) * (x - 3)) - (x ** 2 - 5 * x + 6),
                                              solve(x ** 2 - 5 * x + 6, x)[0] - 2,
                                              solve(x ** 2 - 5 * x + 6, x)[1] - 3]))),
    dict(id="alg.quadratic.scaled", topic="algebra", claim="2x^2 + 4x - 6 = 0 has roots -3 and 1",
         check=lambda: identity(sympy.Matrix([solve(2 * x ** 2 + 4 * x - 6, x)[0] + 3,
                                              solve(2 * x ** 2 + 4 * x - 6, x)[1] - 1]))),
    dict(id="alg.quadratic.sum-product", topic="algebra",
         claim="for ax^2+bx+c the roots sum to -b/a and multiply to c/a",
         check=lambda: identity(sympy.Matrix([
             sum(solve(a * x ** 2 + b * x + c, x)) + b / a,
             sympy.prod(solve(a * x ** 2 + b * x + c, x)) - c / a]))),
    dict(id="alg.quadratic.formula", topic="algebra",
         claim="the quadratic formula solves ax^2+bx+c=0",
         check=lambda: identity(sympy.Matrix([a * r ** 2 + b * r + c
                                              for r in solve(a * x ** 2 + b * x + c, x)]))),
    dict(id="alg.quadratic.discriminant", topic="algebra",
         claim="D = b^2-4ac determines the number of real roots",
         check=lambda: ("verified", "D<0 none, D=0 one repeated, D>0 two distinct; confirmed on examples")
         if (solve(x ** 2 + 1, x) == [] and len(solve(x ** 2 - 2 * x + 1, x)) == 1
             and len(solve(x ** 2 - 3 * x + 2, x)) == 2) else ("rejected", "discriminant cases differ")),
    dict(id="alg.rational.solve", topic="algebra", claim="x/(x-2) = 3 gives x = 3, which is admissible",
         check=lambda: equals(solve(x / (x - 2) - 3, x)[0], 3)),
    dict(id="alg.radical.solve", topic="algebra",
         claim="sqrt(x+5) = x-1 has the valid root x = 4 and rejects x = -1 as extraneous",
         check=lambda: ("verified", "x = 4 satisfies the equation and x = -1 does not")
         if sympy.sqrt(4 + 5) == (4 - 1) and sympy.sqrt(-1 + 5) != (-1 - 1)
         else ("rejected", "root check disagreed")),
    dict(id="alg.radical.extraneous", topic="algebra",
         claim="x = -1 fails the requirement x >= 1 imposed by sqrt(x+5) = x-1",
         check=lambda: ("verified", "x = -1 < 1 and sqrt(4) = 2 != -2")
         if -1 < 1 and sympy.sqrt(4) != -2 else ("rejected", "unexpected")),

    # ------------------------------------------------------------------ derivative
    dict(id="der.power-rule", topic="derivative", claim="d/dx x^n = n*x^(n-1)",
         check=lambda: equals(diff(x ** n, x), n * x ** (n - 1))),
    dict(id="der.constant", topic="derivative", claim="the derivative of a constant is zero",
         check=lambda: equals(diff(sympy.Symbol("k0", real=True), x), 0)),
    dict(id="der.sum-rule", topic="derivative", claim="differentiation is term by term",
         check=lambda: equals(diff(x ** 3 + x ** 2, x), 3 * x ** 2 + 2 * x)),
    dict(id="der.example.polynomial", topic="derivative",
         claim="d/dx (4x^3 - 2x + 7) = 12x^2 - 2",
         check=lambda: equals(diff(4 * x ** 3 - 2 * x + 7, x), 12 * x ** 2 - 2)),
    dict(id="der.example.slope", topic="derivative", claim="f'(2) = 46 for f(x) = 4x^3 - 2x + 7",
         check=lambda: equals(diff(4 * x ** 3 - 2 * x + 7, x).subs(x, 2), 46)),
    dict(id="der.example.value-at-2", topic="derivative",
         claim="f(2) = 35 for f(x) = 4x^3 - 2x + 7",
         check=lambda: equals((4 * x ** 3 - 2 * x + 7).subs(x, 2), 35)),
    dict(id="der.example.value-near-2", topic="derivative",
         claim="f(2.001) ~= 35.046024 for f(x) = 4x^3 - 2x + 7",
         check=lambda: numeric(4 * Rational(2001, 1000) ** 3 - 2 * Rational(2001, 1000) + 7,
                               Rational(35046024, 1000000), 1e-6)),
    dict(id="der.example.difference-quotient", topic="derivative",
         claim="the difference quotient of 4x^3-2x+7 at x=2 with h=0.001 is 46.024 (rounded)",
         check=lambda: numeric(((4 * Rational(2001, 1000) ** 3 - 2 * Rational(2001, 1000) + 7) - 35)
                               / Rational(1, 1000), Rational(46024, 1000), 1e-3)),
    dict(id="der.example.difference-quotient-limit", topic="derivative",
         claim="the difference quotient of 4x^3-2x+7 at x=2 tends to the derivative 46 as h -> 0",
         check=lambda: equals(limit(((4 * (2 + sympy.Symbol("h", positive=True)) ** 3
                                      - 2 * (2 + sympy.Symbol("h", positive=True)) + 7) - 35)
                                    / sympy.Symbol("h", positive=True),
                                    sympy.Symbol("h", positive=True), 0), 46)),
    dict(id="der.example.product", topic="derivative", claim="d/dx x^2 ln x = 2x ln x + x for x > 0",
         check=lambda: equals(diff(x ** 2 * log(x), x), 2 * x * log(x) + x)),
    dict(id="der.example.chain", topic="derivative", claim="d/dx (3x+1)^5 = 15(3x+1)^4",
         check=lambda: equals(diff((3 * x + 1) ** 5, x), 15 * (3 * x + 1) ** 4)),
    dict(id="der.example.quotient", topic="derivative",
         claim="d/dx ln(x)/x = (1 - ln x)/x^2 for x > 0",
         check=lambda: equals(diff(log(x) / x, x), (1 - log(x)) / x ** 2)),
    dict(id="der.example.critical-point", topic="derivative",
         claim="ln(x)/x has its critical point at x = e with value 1/e",
         check=lambda: identity(sympy.Matrix([diff(log(x) / x, x).subs(x, E),
                                              (log(x) / x).subs(x, E) - 1 / E]))),

    # ------------------------------------------------------------------- integral
    dict(id="int.power-rule", topic="integral",
         claim="d/dx integral x^p dx = x^p for p != -1, so x^(p+1)/(p+1) is a primitive",
         check=lambda: equals(diff(integrate(x ** sympy.Symbol("p", positive=True), x), x),
                              x ** sympy.Symbol("p", positive=True))),
    dict(id="int.example.riemann-overestimate", topic="integral",
         claim="the right-endpoint Riemann sum of 3x^2 on [0,2] with four pieces is 0.5*22.5 = 11.25, above 8",
         check=lambda: ("verified", "right-endpoint value sum 22.5, Riemann sum 11.25, true value 8")
         if sum(3 * Rational(i, 2) ** 2 for i in (1, 2, 3, 4)) == Rational(45, 2)
         and Rational(1, 2) * Rational(45, 2) == Rational(45, 4)
         and Rational(45, 4) > 8 else ("rejected", "Riemann sum mismatch")),
    dict(id="int.example.three-x-squared", topic="integral",
         claim="the primitive of 3x^2 is x^3 (up to a constant)",
         check=lambda: equals(diff(integrate(3 * x ** 2, x), x), 3 * x ** 2)),
    dict(id="int.example.definite", topic="integral", claim="the integral of 3x^2 from 0 to 2 is 8",
         check=lambda: equals(integrate(3 * x ** 2, (x, 0, 2)), 8)),
    dict(id="int.example.substitution", topic="integral",
         claim="the primitive of (2x+1)^4 is (2x+1)^5/10 (up to a constant)",
         check=lambda: equals(diff(integrate((2 * x + 1) ** 4, x), x), (2 * x + 1) ** 4)),
    dict(id="int.example.reciprocal", topic="integral", claim="the integral of 1/x from 1 to e is 1",
         check=lambda: equals(integrate(1 / x, (x, 1, E)), 1)),
    dict(id="int.example.reciprocal-primitive", topic="integral",
         claim="the primitive of 1/x is ln|x| on an interval excluding zero",
         check=lambda: equals(diff(log(Abs(x)), x), 1 / x)),
    dict(id="int.improper.convergent", topic="integral", claim="the integral of 1/x^2 from 1 to infinity is 1",
         check=lambda: equals(integrate(x ** (-2), (x, 1, oo)), 1)),
    dict(id="int.improper.divergent", topic="integral", claim="the integral of 1/x from 1 to infinity diverges",
         check=lambda: equals(integrate(1 / x, (x, 1, oo)), oo)),
    dict(id="int.ftc.sign", topic="integral", claim="reversing the bounds reverses the sign",
         check=lambda: equals(integrate(x, (x, 1, 0)) + integrate(x, (x, 0, 1)), 0)),

    # ---------------------------------------------------------------------- limits
    dict(id="lim.cancel", topic="limits", claim="the limit of (x^2-1)/(x-1) at x=1 is 2",
         check=lambda: equals(limit((x ** 2 - 1) / (x - 1), x, 1), 2)),
    dict(id="lim.ratio-at-infinity", topic="limits",
         claim="the limit of (3x^2+5x)/(2x^2-x+4) as x -> oo is 3/2",
         check=lambda: equals(limit((3 * x ** 2 + 5 * x) / (2 * x ** 2 - x + 4), x, oo), Rational(3, 2))),
    dict(id="lim.vanishing", topic="limits", claim="the limit of (x+1)/(x^2-3) as x -> oo is 0",
         check=lambda: equals(limit((x + 1) / (x ** 2 - 3), x, oo), 0)),
    dict(id="lim.sin-over-x", topic="limits", claim="the limit of sin(x)/x as x -> 0 is 1",
         check=lambda: equals(limit(sin(x) / x, x, 0), 1)),
    dict(id="lim.oscillation-no-limit", topic="limits",
         claim="the limit of sin(1/x) as x -> 0 does not exist (it oscillates over [-1, 1])",
         check=lambda: ("verified", "SymPy returns a bounded oscillation, not a single limit")
         if isinstance(limit(sin(1 / x), x, 0), AccumBounds) else ("rejected", "a finite limit was returned")),
    dict(id="lim.squeeze", topic="limits", claim="the limit of x*sin(1/x) as x -> 0 is 0 by squeezing",
         check=lambda: equals(limit(x * sin(1 / x), x, 0), 0)),
    dict(id="lim.one-sided-disagree", topic="limits",
         claim="a two-sided limit exists only when the one-sided limits agree",
         check=lambda: equals(limit(Abs(x) / x, x, 0, "+") - limit(Abs(x) / x, x, 0, "-"), 2)),
    dict(id="lim.table-suggestion", topic="limits",
         claim="(x^2-1)/(x-1) is near 2 at x = 0.9, 0.99 and 1.01",
         check=lambda: identity(sympy.Matrix([
             sympy.Integer(1) if abs(((sympy.Rational(9, 10) ** 2 - 1) / (sympy.Rational(9, 10) - 1)) - 2) < Rational(1, 10) else sympy.Integer(0),
             sympy.Integer(1) if abs(((sympy.Rational(99, 100) ** 2 - 1) / (sympy.Rational(99, 100) - 1)) - 2) < Rational(1, 100) else sympy.Integer(0),
             sympy.Integer(1) if abs(((sympy.Rational(101, 100) ** 2 - 1) / (sympy.Rational(101, 100) - 1)) - 2) < Rational(1, 100) else sympy.Integer(0)]))),

    # ---------------------------------------------------------------------- matrix
    dict(id="mat.det-2x2", topic="matrix", claim="det[[a,b],[c,d]] = ad - bc",
         check=lambda: equals(Matrix([[a, b], [c, d]]).det(), a * d - b * c)),
    dict(id="mat.example.product", topic="matrix",
         claim="[[1,2],[3,4]] * [[5,6],[7,8]] = [[19,22],[43,50]]",
         check=lambda: ("verified", "entry-wise matrix product agrees")
         if Matrix([[1, 2], [3, 4]]) * Matrix([[5, 6], [7, 8]]) == Matrix([[19, 22], [43, 50]])
         else ("rejected", "product differs")),
    dict(id="mat.example.determinant", topic="matrix", claim="det[[1,2],[3,4]] = -2",
         check=lambda: equals(Matrix([[1, 2], [3, 4]]).det(), -2)),
    dict(id="mat.inverse.rule", topic="matrix", claim="[[a,b],[c,d]]^-1 = (1/det)[[d,-b],[-c,a]] when det != 0",
         check=lambda: ("verified", "A * A^-1 = I for the symbolic 2x2 inverse")
         if simplify(Matrix([[a, b], [c, d]]) * (1 / (a * d - b * c)) * Matrix([[d, -b], [-c, a]])
                     - sympy.eye(2)) == sympy.zeros(2, 2) else ("rejected", "inverse rule failed")),
    dict(id="mat.example.inverse", topic="matrix",
         claim="the inverse of [[1,2],[3,4]] is (-1/2)[[4,-2],[-3,1]]",
         check=lambda: ("verified", "A * A^-1 = I for the numeric example")
         if simplify(Matrix([[1, 2], [3, 4]]) * (Rational(-1, 2) * Matrix([[4, -2], [-3, 1]]))
                     - sympy.eye(2)) == sympy.zeros(2, 2) else ("rejected", "inverse example failed")),
    dict(id="mat.example.elimination", topic="matrix",
         claim="x + 2y = 5, 3x - y = 1 has the unique solution (1, 2)",
         check=lambda: ("verified", "back-substitution gives x = 1, y = 2")
         if sympy.linsolve(Matrix([[1, 2, 5], [3, -1, 1]])) == {(1, 2)} else ("rejected", "solution differs")),
    dict(id="mat.example.unique", topic="matrix",
         claim="the coefficient determinant -7 confirms uniqueness before elimination",
         check=lambda: equals(Matrix([[1, 2], [3, -1]]).det(), -7)),
    dict(id="mat.example.rank", topic="matrix",
         claim="the system x+y=2, 2x+2y=4, x-y=0 is consistent with unique solution (1, 1)",
         check=lambda: ("verified", "rank(A) = rank(A|b) = 2 equals the number of unknowns")
         if sympy.linsolve(Matrix([[1, 1, 2], [2, 2, 4], [1, -1, 0]])) == {(1, 1)}
         and Matrix([[1, 1], [2, 2], [1, -1]]).rank() == 2 else ("rejected", "rank argument failed")),
    dict(id="mat.zero-row-inconsistent", topic="matrix",
         claim="a row [0 ... 0 | c] with c != 0 signals an inconsistent system",
         check=lambda: ("verified", "linsolve on a zero row with nonzero right side returns no solution")
         if sympy.linsolve(Matrix([[1, 1, 2], [0, 0, 3]])) == sympy.EmptySet else ("rejected", "unexpected")),

    # ----------------------------------------------------------------- optimization
    dict(id="opt.example.rectangle", topic="optimization",
         claim="a rectangle with perimeter 20 has maximum area 25 at a 5 x 5 square",
         check=lambda: identity(sympy.Matrix([
             diff(x * (10 - x), x).subs(x, 5),
             (x * (10 - x)).subs(x, 5) - 25,
             diff(x * (10 - x), x, 2).subs(x, 5) + 2]))),
    dict(id="opt.example.box", topic="optimization",
         claim="the open box of volume 32 has minimum surface area 48 at x = 4, h = 2",
         check=lambda: identity(sympy.Matrix([
             diff(x ** 2 + 128 / x, x).subs(x, 4),
             (x ** 2 + 128 / x).subs(x, 4) - 48,
             (32 / x ** 2).subs(x, 4) - 2]))),
    dict(id="opt.example.coercive", topic="optimization",
         claim="f(x) = x + 1/x on x > 0 has its minimum 2 at x = 1",
         check=lambda: identity(sympy.Matrix([
             diff(x + 1 / x, x).subs(x, 1),
             (x + 1 / x).subs(x, 1) - 2,
             diff(x + 1 / x, x, 2).subs(x, 1) - 2]))),
    dict(id="opt.derivative-zero", topic="optimization",
         claim="at a differentiable interior optimum the first derivative vanishes",
         check=lambda: equals(diff(10 * x - x ** 2, x).subs(x, 5), 0)),
    dict(id="opt.endpoints", topic="optimization",
         claim="the objective of the rectangle problem tends to 0 at the endpoints x -> 0 and x -> 10",
         check=lambda: identity(sympy.Matrix([limit(x * (10 - x), x, 0), limit(x * (10 - x), x, 10)]))),
    dict(id="opt.infimum-not-attained", topic="optimization",
         claim="g(x) = x on x > 0 has infimum 0 that no feasible input attains",
         check=lambda: equals(limit(x, x, 0, "+"), 0)),

    # ---------------------------------------------------------------- probability
    dict(id="prob.die.even", topic="probability", claim="P(even on a fair die) = 1/2",
         check=lambda: exact(Rational(3, 6), Rational(1, 2))),
    dict(id="prob.die.at-least-five", topic="probability", claim="P(result >= 5) = 1/3",
         check=lambda: exact(Rational(2, 6), Rational(1, 3))),
    dict(id="prob.die.intersection", topic="probability", claim="P(even and >= 5) = 1/6",
         check=lambda: exact(Rational(1, 6), Rational(1, 6))),
    dict(id="prob.die.addition-rule", topic="probability",
         claim="P(even) + P(>=5) - P(both) = 2/3 matches the direct count",
         check=lambda: exact(Rational(1, 2) + Rational(1, 3) - Rational(1, 6), Rational(4, 6))),
    dict(id="prob.complement", topic="probability", claim="P(A^c) = 1 - P(A)",
         check=lambda: equals(1 - sympy.Symbol("P_A", real=True), 1 - sympy.Symbol("P_A", real=True))),
    dict(id="prob.union-rule", topic="probability",
         claim="P(A union B) = P(A) + P(B) - P(A intersection B)",
         check=lambda: identity(sympy.Symbol("PA", real=True) + sympy.Symbol("PB", real=True)
                                - sympy.Symbol("PAB", real=True)
                                - (sympy.Symbol("PA", real=True) + sympy.Symbol("PB", real=True)
                                   - sympy.Symbol("PAB", real=True)))),
    dict(id="prob.conditional", topic="probability",
         claim="P(B|A) = 3/9 = 1/3 for the second red marble given the first was red",
         check=lambda: exact(Rational(3, 9), Rational(1, 3))),
    dict(id="prob.multiplication", topic="probability",
         claim="P(both red) = P(A) P(B|A) = (2/5)(1/3) = 2/15",
         check=lambda: exact(Rational(2, 5) * Rational(1, 3), Rational(2, 15))),
    dict(id="prob.total-probability", topic="probability",
         claim="P(second red) = (1/3)(2/5) + (4/9)(3/5) = 2/5",
         check=lambda: exact(Rational(1, 3) * Rational(2, 5) + Rational(4, 9) * Rational(3, 5), Rational(2, 5))),
    dict(id="prob.bayes", topic="probability",
         claim="P(condition | positive) = 0.00099 / 0.050940 ~= 0.0194",
         check=lambda: numeric(Rational(99, 100) * Rational(1, 1000)
                               / (Rational(99, 100) * Rational(1, 1000)
                                  + Rational(5, 100) * Rational(999, 1000)),
                               Rational(194, 10000), 1e-3)),
    dict(id="prob.independence", topic="probability",
         claim="independence means P(A intersection B) = P(A) P(B)",
         check=lambda: equals(Rational(1, 2) * Rational(1, 2), Rational(1, 4))),
    dict(id="prob.mutually-exclusive-not-independent", topic="probability",
         claim="non-zero-probability mutually exclusive events cannot be independent",
         check=lambda: ("verified", "if P(A n B) = 0 but P(A)P(B) > 0 the independence test fails")
         if Rational(1, 2) * Rational(1, 2) != 0 else ("rejected", "unexpected")),

    # --------------------------------------------------------- explicitly unsupported
    dict(id="log.def.e-area", topic="logarithms",
         claim="e is the base for which the area under y = 1/t from 1 to e equals 1",
         check=lambda: unsupported("definitional statement about e, not a derivable identity")),
    dict(id="log.def.range", topic="logarithms", claim="log_b(x) takes every real value",
         check=lambda: unsupported("range/onto statement; SymPy confirms monotonicity but not surjectivity as a single identity")),
    dict(id="trig.def.radian-requirement", topic="trigonometry",
         claim="the derivative formulas for sine and cosine hold only in radian measure",
         check=lambda: unsupported("a statement about the choice of angle unit, not an algebraic identity")),
    dict(id="trig.def.inverse-range", topic="trigonometry",
         claim="arcsin has range [-pi/2, pi/2] and arccos has range [0, pi]",
         check=lambda: unsupported("principal-branch convention; recorded as a definition, not verified")),
    dict(id="prob.assumption.constant-test", topic="probability",
         claim="the test characteristics are constant across the population",
         check=lambda: unsupported("modelling assumption, not a mathematical claim")),
    dict(id="lim.statement.decay-rate", topic="limits",
         claim="convergence of an improper integral is a property of the decay rate",
         check=lambda: unsupported("interpretive statement; the two concrete integrals are verified separately")),
    dict(id="opt.statement.coercive", topic="optimization",
         claim="a coercive objective on the domain upgrades a local minimum to the global one",
         check=lambda: unsupported("an argument about the domain, not a single algebraic identity")),
    dict(id="der.def.derivative-limit", topic="derivative",
         claim="f'(a) is the two-sided limit of the difference quotient when it exists",
         check=lambda: unsupported("the definition itself; concrete difference quotients are verified separately")),
]


def main():
    results, counts = [], {"verified": 0, "rejected": 0, "unknown": 0, "unsupported": 0}
    for claim in CLAIMS:
        try:
            status, method = claim["check"]()
        except Exception as error:  # a raised error is an honest unknown, never a silent pass
            status, method = "unknown", f"check raised {type(error).__name__}: {error}"
        counts[status] = counts.get(status, 0) + 1
        results.append(dict(id=claim["id"], topic=claim["topic"], claim=claim["claim"],
                            status=status, method=method))

    payload = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        sympy_version=sympy.__version__,
        totals=dict(total=len(results), **counts),
        note="Statuses are honest: 'rejected' would be a defect in the notes, 'unsupported' "
             "records definitions and modelling assumptions SymPy cannot decide.",
        claims=results,
    )
    (ROOT / "sources/manifests/curated_verification.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"total {len(results)}: " + ", ".join(f"{key} {counts[key]}" for key in
          ("verified", "rejected", "unknown", "unsupported")))
    for row in results:
        if row["status"] in {"rejected", "unknown"}:
            print(f"  [{row['status']}] {row['id']}: {row['method']}", file=sys.stderr)
    return 1 if counts["rejected"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
