import { z } from "zod";
import { geometryParamsSchema, type GeometryState } from "./geometry";

const finite = z.number().finite();
const inputNumber = finite.min(-1_000_000).max(1_000_000);
const plain = (max: number) => z.string().min(1).max(max).refine(value => !/[<>`$#*]|https?:\/\/|javascript:|data:|[\x00-\x08\x0b\x0c\x0e-\x1f]/i.test(value));
const label = (max: number) => z.string().max(max).refine(value => !/[<>`]|[\x00-\x1f]/.test(value));
const domain = z.object({min: inputNumber, max: inputNumber}).strict().refine(value => value.max > value.min && value.max - value.min <= 200);
const expression = z.object({label: plain(24), expression: z.string().min(1).max(1024)}).strict();
const slider = z.object({name: z.string().regex(/^[A-Za-z][A-Za-z0-9_]{0,11}$/), min: inputNumber, max: inputNumber,
  step: finite.positive(), default: inputNumber}).strict().refine(value => value.min < value.max && value.step <= value.max - value.min && value.default >= value.min && value.default <= value.max);
const highlight = z.object({x: inputNumber, label: label(40)}).strict();
const point = z.object({x: inputNumber, y: finite}).strict();
const gap = z.object({from: inputNumber, to: inputNumber, reason: z.enum(["undefined", "discontinuity", "out_of_range"])}).strict().refine(value => value.to >= value.from);
export const sampleSchema = z.object({status: z.enum(["ok", "invalid_expression"]),
  series: z.array(z.object({label: label(24), points: z.array(point).max(2000), gaps: z.array(gap).max(4001)}).strict()).max(3),
  highlight_points: z.array(point.extend({label: label(40), series_index: z.number().int().min(0).max(2)})).max(15),
  domain_warnings: z.array(z.string().max(300)).max(24)}).strict();
const envelope = {id: z.string().regex(/^blk_[0-7][0-9A-HJKMNP-TV-Z]{25}$/), version: z.literal(1), title: plain(120), fallback_text: plain(600)};
const graphParams = z.object({expressions: z.array(expression).min(1).max(3), variable: z.literal("x"), domain,
  parameters: z.array(slider).max(4), highlight_points: z.array(highlight).max(5), sample_count: z.number().int().min(50).max(2000),
  x_label: label(40), y_label: label(40), y_domain: domain.nullable(), samples: sampleSchema}).strict();
const graphSchema = z.object({...envelope, type: z.literal("function_graph"), data_source: z.literal("sympy_graph_sampler"), params: graphParams}).strict()
  .refine(block => new Set(block.params.parameters.map(p => p.name)).size === block.params.parameters.length)
  .refine(block => validSamples(block.params.samples, block.params));
const step = z.object({step_id: z.string().min(1).max(16).regex(/^[A-Za-z0-9:_-]+$/), state: z.string().min(1).max(1024),
  justification: plain(300), verification: z.enum(["verified", "unsupported", "unknown"])}).strict();
const stepsSchema = z.object({...envelope, type: z.literal("step_reveal"), data_source: z.literal("sympy_step_builder"),
  params: z.object({initial_expression: z.string().min(1).max(1024), final_expression: z.string().min(1).max(1024),
    steps: z.array(step).min(2).max(12), topic: z.string().max(120).nullable()}).strict()}).strict()
  .refine(block => new Set(block.params.steps.map(s => s.step_id)).size === block.params.steps.length);
const geometrySchema=z.object({...envelope,type:z.literal("geometry_canvas"),data_source:z.literal("geometry_engine"),params:geometryParamsSchema}).strict();
export const blockSchema = z.discriminatedUnion("type", [graphSchema, stepsSchema, geometrySchema]);
export type UIBlock = z.infer<typeof blockSchema>;
export type GraphBlock = Extract<UIBlock, {type: "function_graph"}>;
export type StepBlock = Extract<UIBlock, {type: "step_reveal"}>;
export type GeometryBlock = Extract<UIBlock, {type: "geometry_canvas"}>;
export type SampleResult = z.infer<typeof sampleSchema>;
export type GraphState = {kind: "function_graph"; parameters: Record<string, number>; samples?: SampleResult; sampledParameters?: Record<string, number>};
export type StepState = {kind: "step_reveal"; index: number};
export type BlockState = GraphState | StepState | GeometryState;
export type StoredBlock = {id: string; payload: unknown; state?: BlockState};

export function validSamples(samples: SampleResult, params: {expressions: {label: string}[]; domain: {min: number; max: number}; sample_count: number}): boolean {
  return samples.status === "ok" && samples.series.length === params.expressions.length &&
    samples.series.every((series, i) => series.label === params.expressions[i].label && series.points.length <= params.sample_count &&
      series.points.every((p, j) => p.x >= params.domain.min && p.x <= params.domain.max && (j === 0 || p.x > series.points[j-1].x))) &&
    samples.highlight_points.every(point => point.series_index < samples.series.length);
}
export function parametersFor(block: GraphBlock, saved?: BlockState): Record<string, number> {
  return Object.fromEntries(block.params.parameters.map(slider => {
    const value = saved?.kind === "function_graph" ? saved.parameters?.[slider.name] : undefined;
    return [slider.name, typeof value === "number" && Number.isFinite(value) && value >= slider.min && value <= slider.max ? value : slider.default];
  }));
}
export function sameParameters(a: Record<string, number>, b?: Record<string, number>) {
  return !!b && Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(key => a[key] === b[key]);
}
export function fallbackFor(payload: unknown) {
  const value = payload && typeof payload === "object" ? (payload as Record<string, unknown>).fallback_text : undefined;
  return typeof value === "string" && value.trim() ? value.slice(0, 600) : "نمایش این بخش در دسترس نیست. توضیح درس را در متن بالا بخوانید.";
}

// Transform only validated numeric samples to SVG coordinates. Never evaluate
// expressions or derive new function values in the browser.
export function curvePaths(points: {x: number; y: number}[], gaps: {from: number; to: number}[],
  project: (x: number, y: number) => [number, number]): string[] {
  const paths: string[] = []; let current = "", previous: number | undefined;
  for (const point of points) {
    if (gaps.some(gap => point.x >= gap.from && point.x <= gap.to)) { if(current) paths.push(current); current=""; previous=undefined; continue; }
    if (previous !== undefined && gaps.some(gap => gap.from >= previous! && gap.to <= point.x || gap.from < point.x && gap.to > previous!)) {
      if(current) paths.push(current); current="";
    }
    const [x,y] = project(point.x, point.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) {if(current) paths.push(current);current="";previous=undefined;continue;}
    current += `${current ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)} `; previous=point.x;
  }
  if(current) paths.push(current);
  return paths;
}
