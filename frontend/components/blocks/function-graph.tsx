"use client";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { RotateCcw } from "lucide-react";
import { MathText } from "@/components/math-text";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Slider } from "@/components/ui/slider";
import { curvePaths, parametersFor, sameParameters, sampleSchema, validSamples, type GraphBlock, type BlockState, type SampleResult } from "@/lib/ui-blocks";
import type { EventIntent } from "@/lib/ui-events";

const latinNumber = (value: number) => Math.abs(value) >= 10000 || (value !== 0 && Math.abs(value) < 0.001) ? value.toExponential(2) : new Intl.NumberFormat("en-US",{maximumFractionDigits:3,useGrouping:false}).format(value);
const samplingErrors: Record<string,string> = {
  invalid_expression:"این مقادیر برای تابع تعریف نشده‌اند. پایهٔ لگاریتم باید مثبت و نابرابر با 1 باشد.",
  thread_not_found:"جلسهٔ نمودار دیگر روی سرور نیست. نمودار ذخیره‌شده محفوظ است؛ برای تغییر آن، درس را در جلسهٔ تازه ادامه دهید.",
  block_invalid:"تغییر این نمودار در دسترس نیست. دوباره نمودار را در درس تازه‌ای دریافت کنید.",
  rate_limited:"درخواست‌ها خیلی نزدیک به هم بودند. کمی بعد دوباره تلاش کنید.",
  timeout:"آماده‌سازی نمودار بیش از حد طول کشید. دوباره تلاش کنید.",
  network_error:"ارتباط با نمودار برقرار نشد. متن درس محفوظ است؛ دوباره تلاش کنید.",
};

export function FunctionGraph({block,threadId,state,onChange,onEvent,disabled=false}: {block:GraphBlock;threadId:string;state?:BlockState;onChange:(state:BlockState)=>void;onEvent?:(event:EventIntent)=>void;disabled?:boolean}) {
  const id=useId();
  const parameters=parametersFor(block,state), key=JSON.stringify(parameters);
  const defaults=Object.fromEntries(block.params.parameters.map(p=>[p.name,p.default]));
  const saved=state?.kind === "function_graph" ? sampleSchema.safeParse(state.samples) : null;
  const savedMatches=saved?.success && validSamples(saved.data,block.params) && sameParameters(parameters,state?.kind === "function_graph" ? state.sampledParameters : undefined);
  const samples:SampleResult|null=savedMatches ? saved.data : sameParameters(parameters,defaults) ? block.params.samples : null;
  const [status,setStatus]=useState<"ready"|"loading"|"error">(samples ? "ready":"loading"), [error,setError]=useState(""), [retry,setRetry]=useState(0);
  const changeRef=useRef(onChange); changeRef.current=onChange;
  const samplesRef=useRef(samples); samplesRef.current=samples;
  useEffect(()=>{
    if(disabled) return;
    if(samplesRef.current){setStatus("ready");setError("");return;}
    let active=true; const abort=new AbortController(); let deadline:ReturnType<typeof setTimeout>|undefined;
    setStatus("loading");setError("");
    const timer=setTimeout(async()=>{
      deadline=setTimeout(()=>abort.abort(),65000);
      try {
        const response=await fetch("/api/ui/sample",{method:"POST",headers:{"Content-Type":"application/json"},signal:abort.signal,
          body:JSON.stringify({thread_id:threadId,block_id:block.id,expressions:block.params.expressions,variable:block.params.variable,
            domain:block.params.domain,parameters,sample_count:block.params.sample_count,highlight_points:block.params.highlight_points})});
        if(!response.ok){let code="network_error";try {code=(await response.json()).error?.code || code;}catch{}throw new Error(code);}
        const result=sampleSchema.parse(await response.json());
        if(result.status!=="ok") throw new Error("invalid_expression");
        if(!validSamples(result,block.params)) throw new Error("network_error");
        if(active){changeRef.current({kind:"function_graph",parameters,samples:result,sampledParameters:parameters});setStatus("ready");}
      } catch(failure) {
        if(active){setError(samplingErrors[abort.signal.aborted ? "timeout" : failure instanceof Error ? failure.message : "network_error"] || samplingErrors.network_error);setStatus("error");}
      } finally {if(deadline)clearTimeout(deadline);}
    },250);
    return()=>{active=false;clearTimeout(timer);if(deadline)clearTimeout(deadline);abort.abort();};
    // Persisting completed samples must not trigger a second sampling request.
    // The desired parameter signature, retry and enablement own this effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[key,retry,disabled,threadId,block.id]);
  return <Card className="ui-block function-graph" data-block-id={block.id} role="region" aria-labelledby={`${id}-title`} dir="rtl">
    <CardHeader><CardTitle><h2 id={`${id}-title`} dir="auto">{block.title}</h2></CardTitle><CardDescription>پارامتر را تغییر دهید و شکل تابع را مقایسه کنید.</CardDescription></CardHeader>
    <CardContent className="graph-content">
      <div className="graph-expressions" dir="ltr">{block.params.expressions.map((expression,i)=><span key={i} className={`graph-legend curve-${i}`}><span aria-hidden="true"/><MathText text={`$${expression.label} =$`}/><code>{expression.expression}</code></span>)}</div>
      <div className="graph-surface" aria-busy={status==="loading"}>
        {status!=="error" && samples ? <GraphPlot block={block} samples={samples}/> : <div className="graph-placeholder">{status==="error" ? "نمودار برای این مقادیر نمایش داده نمی‌شود." : "در حال رسم نمودار…"}</div>}
      </div>
      {status==="loading" && <p className="block-status" role="status">در حال به‌روزرسانی نمودار…</p>}
      {status==="error" && <Alert variant="destructive"><AlertDescription>{error}<Button variant="outline" size="sm" disabled={disabled} onClick={()=>setRetry(n=>n+1)}><RotateCcw data-icon="inline-start"/>تلاش دوباره برای نمودار</Button></AlertDescription></Alert>}
      <FieldGroup className="graph-parameters">{block.params.parameters.map(parameter=><Field key={parameter.name}><div className="parameter-heading"><FieldLabel id={`${id}-${parameter.name}-label`}>پارامتر <span dir="ltr">{parameter.name}</span></FieldLabel><output data-testid={`value-${parameter.name}`} dir="ltr">{latinNumber(parameters[parameter.name])}</output></div>
        <Slider dir="ltr" value={[parameters[parameter.name]]} min={parameter.min} max={parameter.max} step={parameter.step} disabled={disabled}
          aria-labelledby={`${id}-${parameter.name}-label`} aria-valuetext={String(parameters[parameter.name])}
          onValueChange={([value])=>{if(Number.isFinite(value))onChange({kind:"function_graph",parameters:{...parameters,[parameter.name]:value}});}}/>
        <div className="parameter-range" dir="ltr"><span>{latinNumber(parameter.min)}</span><span>{latinNumber(parameter.max)}</span></div></Field>)}</FieldGroup>
      {status==="ready" && samples && <><div className="graph-highlights">{samples.highlight_points.map((point,index)=><span key={index} dir="ltr" data-testid="graph-highlight"><MathText text={`$x = ${latinNumber(point.x)},\\quad ${block.params.expressions[point.series_index].label} = ${latinNumber(point.y)}$`}/></span>)}</div>
        {samples.domain_warnings.length>0 && <p className="block-note">بعضی نقطه‌ها در این دامنه تعریف نشده‌اند و روی نمودار نمایش داده نمی‌شوند.</p>}
</>}
    </CardContent><CardFooter>{onEvent && <Button variant="outline" disabled={disabled || status!=="ready" || !samples} onClick={()=>onEvent({type:"graph_question",block_id:block.id,payload:{params:parameters}})}>دربارهٔ این نمودار بپرس</Button>}{onEvent && status==="error" && <Button variant="outline" disabled={disabled} onClick={()=>onEvent({type:"block_error",block_id:block.id,payload:{code:"sampling_failed"}})}>ادامه با متن</Button>}</CardFooter>
  </Card>;
}

function GraphPlot({block,samples}:{block:GraphBlock;samples:SampleResult}) {
  const id=useId().replace(/[^A-Za-z0-9_-]/g,"");
  const geometry=useMemo(()=>{
    const ys=samples.series.flatMap(series=>series.points.map(p=>p.y)).sort((a,b)=>a-b);
    let bottom=block.params.y_domain?.min ?? ys[Math.floor(ys.length*0.03)] ?? -1;
    let top=block.params.y_domain?.max ?? ys[Math.floor(ys.length*0.97)] ?? 1;
    if(top===bottom){const padding=Math.max(1,Math.abs(top)*0.1);bottom-=padding;top+=padding;}
    if(!Number.isFinite(top-bottom) || top<=bottom) throw new Error("plot_range");
    if(!block.params.y_domain){const margin=(top-bottom)*0.1;bottom-=margin;top+=margin;}
    if(!Number.isFinite(top) || !Number.isFinite(bottom) || !Number.isFinite(top-bottom)) throw new Error("plot_range");
    const left=block.params.domain.min,right=block.params.domain.max;
    const project=(x:number,y:number):[number,number]=>[58+(x-left)/(right-left)*604,260-(y-bottom)/(top-bottom)*232];
    return {bottom,top,left,right,project,paths:samples.series.map(series=>curvePaths(series.points,series.gaps,project))};
  },[block,samples]);
  const {bottom,top,left,right,project,paths}=geometry;
  const ticks=Array.from({length:5},(_,i)=>i/4);
  return <svg className="function-plot" viewBox="0 0 720 306" role="img" aria-labelledby={`${id}-title ${id}-desc`}>
    <title id={`${id}-title`}>{block.title}</title><desc id={`${id}-desc`}>{block.fallback_text} منحنی تابع از داده‌های محاسبه‌شده رسم شده است. ناحیه‌های تعریف‌نشده خالی هستند.</desc>
    <defs><clipPath id={`${id}-clip`}><rect x="58" y="28" width="604" height="232"/></clipPath></defs>
    {ticks.map((t,i)=>{const [x,y]=[58+t*604,260-t*232];return <g key={i} className="plot-grid"><line x1={x} x2={x} y1="28" y2="260"/><line x1="58" x2="662" y1={y} y2={y}/><text x={x} y="281" textAnchor="middle">{latinNumber(left+(right-left)*t)}</text><text x="49" y={y+4} textAnchor="end">{latinNumber(bottom+(top-bottom)*t)}</text></g>;})}
    <g className="plot-axes"><line x1="58" x2="662" y1={project(left,Math.min(top,Math.max(bottom,0)))[1]} y2={project(left,Math.min(top,Math.max(bottom,0)))[1]}/><line x1={project(Math.min(right,Math.max(left,0)),bottom)[0]} x2={project(Math.min(right,Math.max(left,0)),bottom)[0]} y1="28" y2="260"/></g>
    <g clipPath={`url(#${id}-clip)`}>{samples.series.map((series,i)=><g key={i} className={`curve-${i}`}>{series.gaps.map((gap,j)=><rect key={j} className="plot-gap" x={project(gap.from,bottom)[0]} y="28" width={Math.max(1,project(gap.to,bottom)[0]-project(gap.from,bottom)[0])} height="232"/>)}{paths[i].map((path,j)=><path data-testid="curve-path" key={j} d={path} className="plot-curve"/>)}</g>)}{samples.highlight_points.map((point,i)=>{const [x,y]=project(point.x,point.y);return <circle key={i} cx={x} cy={y} r="4" className={`plot-highlight curve-${point.series_index}`}/>;})}</g>
    <text className="plot-axis-label" x="696" y="282" textAnchor="end">{block.params.x_label || "x"}</text><text className="plot-axis-label" x="48" y="16" textAnchor="end">{block.params.y_label || "y"}</text>
  </svg>;
}
