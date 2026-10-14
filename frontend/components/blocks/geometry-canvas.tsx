"use client";
import { useEffect, useId, useRef, useState, type PointerEvent } from "react";
import { RotateCcw } from "lucide-react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Slider } from "@/components/ui/slider";
import { geometryResultSchema, moveGeometryPoint, sameScene, sceneFor, type GeometryScene, type GeometryResult } from "@/lib/geometry";
import type { GeometryBlock, BlockState } from "@/lib/ui-blocks";
import type { EventIntent } from "@/lib/ui-events";

const number=(value:number)=>new Intl.NumberFormat("en-US",{maximumFractionDigits:4,useGrouping:false}).format(value);
const labels:Record<string,[string,string]>={angle_deg:["زاویه","Angle"],angle_rad:["زاویه به رادیان","Angle in radians"],cos:["کسینوس","Cosine"],sin:["سینوس","Sine"],
  length_AB:["ضلع AB","Side AB"],length_BC:["ضلع BC","Side BC"],length_CA:["ضلع CA","Side CA"],angle_A:["زاویه A","Angle A"],angle_B:["زاویه B","Angle B"],angle_C:["زاویه C","Angle C"],
  perimeter:["محیط","Perimeter"],area:["مساحت","Area"],length_u:["طول u","Length of u"],length_v:["طول v","Length of v"],length_sum:["طول u+v","Length of u+v"],dot:["ضرب داخلی","Dot product"],between:["زاویه بین بردارها","Angle between vectors"]};

export function GeometryCanvas({block,threadId,state,onChange,onEvent,disabled=false}:{block:GeometryBlock;threadId:string;state?:BlockState;onChange:(state:BlockState)=>void;onEvent?:(event:EventIntent)=>void;disabled?:boolean}) {
  const id=useId().replace(/[^A-Za-z0-9_-]/g,"");
  const fa=block.params.language==="fa",t=(persian:string,english:string)=>fa?persian:english;
  const scene=sceneFor(block.params.scene,state?.kind==="geometry_canvas"?state:undefined),key=JSON.stringify(scene);
  const saved=state?.kind==="geometry_canvas"?geometryResultSchema.safeParse(state.geometry):null;
  const cached=saved?.success&&sameScene(saved.data.scene,scene)?saved.data:sameScene(scene,block.params.scene)?block.params.geometry:null;
  const previous=useRef<GeometryResult>(cached||block.params.geometry);
  if(cached)previous.current=cached;
  const data=cached||previous.current,matching=sameScene(data.scene,scene);
  const [status,setStatus]=useState<"ready"|"loading"|"error">("ready"),[error,setError]=useState(""),[retry,setRetry]=useState(0);
  const change=useRef(onChange);change.current=onChange;
  const current=useRef({scene,cached});current.current={scene,cached};
  const drag=useRef<{id:string;bounds:{min:number;max:number}}|null>(null);
  const [dragging,setDragging]=useState(false);
  const update=(next:GeometryScene)=>{if(!disabled)change.current({kind:"geometry_canvas",scene:next});};
  useEffect(()=>{
    if(disabled||current.current.cached){setStatus("ready");return;}
    let active=true;const abort=new AbortController();
    setStatus("loading");setError("");
    const timer=setTimeout(async()=>{
      try {
        const response=await fetch("/api/ui/geometry",{method:"POST",headers:{"Content-Type":"application/json"},
          body:JSON.stringify({thread_id:threadId,block_id:block.id,scene:current.current.scene}),signal:AbortSignal.any([abort.signal,AbortSignal.timeout(15000)])});
        if(!response.ok){let code="network_error";try{code=(await response.json()).error?.code||code;}catch{}throw new Error(code);}
        const result=geometryResultSchema.parse(await response.json());
        if(!sameScene(result.scene,scene))throw new Error("network_error");
        if(active){previous.current=result;change.current({kind:"geometry_canvas",scene,geometry:result});setStatus("ready");}
      } catch(failure) {
        if(active){setError(failure instanceof Error?failure.message:"network_error");setStatus("error");}
      }
    },150);
    return()=>{active=false;clearTimeout(timer);abort.abort();};
    // Persisted results do not start another calculation for the same scene.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[key,retry,disabled,threadId,block.id]);
  const viewBounds=dragging&&drag.current?drag.current.bounds:data.bounds;
  const min=viewBounds.min,max=viewBounds.max,size=472;
  const project=(x:number,y:number)=>[64+(x-min)/(max-min)*size,504-(y-min)/(max-min)*size];
  const positions=new Map(data.points.map(p=>[p.id,project(p.x,p.y)]));
  const move=(event:PointerEvent<SVGSVGElement>)=>{
    if(!drag.current||disabled)return;
    const svg=event.currentTarget,matrix=svg.getScreenCTM();if(!matrix)return;
    const p=svg.createSVGPoint();p.x=event.clientX;p.y=event.clientY;
    const q=p.matrixTransform(matrix.inverse()),bounds=drag.current.bounds;
    update(moveGeometryPoint(scene,drag.current.id,bounds.min+(q.x-64)/size*(bounds.max-bounds.min),bounds.min+(504-q.y)/size*(bounds.max-bounds.min)));
  };
  const controls=scene.kind==="triangle"?scene.vertices.map((p,i)=>({id:"ABC"[i],...p})):scene.kind==="vectors"?[{id:"U",...scene.u},{id:"V",...scene.v}]:[];
  const errorText=error==="thread_not_found"?t("جلسه این شکل روی سرور پایان یافته است؛ شکل ذخیره‌شده محفوظ است. درس را در گفت‌وگوی تازه ادامه بده.","This scene's server session has ended; the saved diagram remains. Continue in a new chat."):
    error==="rate_limited"?t("کمی صبر کن و دوباره امتحان کن.","Wait a moment and try again."):t("به‌روزرسانی شکل انجام نشد. شکل قبلی محفوظ است؛ دوباره امتحان کن.","The diagram could not update. The previous diagram is preserved; try again.");
  return <Card className="ui-block geometry-canvas" data-block-id={block.id} role="region" aria-labelledby={`${id}-title`} dir={fa?"rtl":"ltr"}>
    <CardHeader><CardTitle><h2 id={`${id}-title`} dir="auto">{block.title}</h2></CardTitle><CardDescription>{t("نقطه را بکش یا از کنترل‌ها و کلیدهای جهت‌دار استفاده کن.","Drag a point or use the controls and arrow keys.")}</CardDescription></CardHeader>
    <CardContent className="geometry-content">
      <div className="geometry-surface" aria-busy={!matching}>
        <svg viewBox="0 0 600 560" className={matching?"geometry-plot":"geometry-plot geometry-pending"} role="group" aria-labelledby={`${id}-svg-title ${id}-desc`} onPointerMove={move} onPointerUp={()=>{drag.current=null;setDragging(false);}} onPointerCancel={()=>{drag.current=null;setDragging(false);}}>
          <title id={`${id}-svg-title`}>{block.title}</title><desc id={`${id}-desc`}>{t("شکل هندسی و اندازه‌ها در بخش توضیح متنی نیز آمده‌اند. کلیدهای جهت‌دار نقطه انتخاب‌شده را جابه‌جا می‌کنند.","The diagram and measurements also have a text alternative. Arrow keys move the focused point.")}</desc>
          <defs><marker id={`${id}-arrow`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z"/></marker></defs>
          {[0,.25,.5,.75,1].map((v,i)=>{const x=64+v*size,y=504-v*size;return <g key={i} className="plot-grid"><line x1={x} x2={x} y1="32" y2="504"/><line x1="64" x2="536" y1={y} y2={y}/><text x={x} y="530" textAnchor="middle">{number(min+v*(max-min))}</text><text x="54" y={y+4} textAnchor="end">{number(min+v*(max-min))}</text></g>;})}
          <g className="plot-axes"><line x1="64" x2="536" y1={project(0,0)[1]} y2={project(0,0)[1]}/><line x1={project(0,0)[0]} x2={project(0,0)[0]} y1="32" y2="504"/></g>
          {data.circles.map((c,i)=>{const [x,y]=positions.get(c.center)!;return <circle key={i} className="geometry-circle" cx={x} cy={y} r={c.radius/(max-min)*size}/>;})}
          {scene.kind==="triangle"&&<polygon className="geometry-fill" points={data.points.map(p=>positions.get(p.id)!.join(",")).join(" ")}/>}
          {data.segments.map((s,i)=>{const [x1,y1]=positions.get(s.start)!,[x2,y2]=positions.get(s.end)!;return <line key={i} className={`geometry-edge geometry-${s.style}`} x1={x1} y1={y1} x2={x2} y2={y2} markerEnd={s.style==="vector"?`url(#${id}-arrow)`:undefined}/>;})}
          {data.arcs.map((a,i)=><polyline key={i} className="geometry-arc" points={a.points.map(p=>project(p.x,p.y).join(",")).join(" ")}/>)}
          {data.points.map(p=>{const [x,y]=positions.get(p.id)!;return p.draggable?<g key={p.id} className="geometry-handle" transform={`translate(${x},${y})`} role="button" tabIndex={disabled?-1:0} aria-disabled={disabled} aria-label={t(`جابه‌جایی نقطه ${p.label}`,`Move point ${p.label}`)}
            onPointerDown={e=>{if(disabled)return;e.preventDefault();e.currentTarget.focus();drag.current={id:p.id,bounds:data.bounds};setDragging(true);e.currentTarget.setPointerCapture(e.pointerId);}}
            onLostPointerCapture={()=>{drag.current=null;setDragging(false);}}
            onKeyDown={e=>{if(disabled)return;if(e.key==="Enter"||e.key===" "){e.preventDefault();e.currentTarget.focus();return;}if(!e.key.startsWith("Arrow"))return;e.preventDefault();if(scene.kind==="unit_circle")update({...scene,angle_degrees:Math.max(0,Math.min(360,scene.angle_degrees+(["ArrowLeft","ArrowDown"].includes(e.key)?-1:1)))});else {const value=controls.find(v=>v.id===p.id)!;update(moveGeometryPoint(scene,p.id,value.x+(e.key==="ArrowRight"?.1:e.key==="ArrowLeft"?-.1:0),value.y+(e.key==="ArrowUp"?.1:e.key==="ArrowDown"?-.1:0)));}}}>
            <circle className="geometry-hit" r="54"/><circle className="geometry-node" r="7"/><text x="13" y="-13" className="geometry-label">{p.label}</text>
          </g>:<g key={p.id}><circle className="geometry-static-node" cx={x} cy={y} r="3"/>{p.id!=="H"&&<text x={x+12} y={y-10} className="geometry-label">{p.label}</text>}</g>;})}
          <text className="plot-axis-label" x="568" y="528">x</text><text className="plot-axis-label" x="54" y="20">y</text>
        </svg>
      </div>
      {!matching&&status!=="error"&&<p className="block-status" role="status">{t("در حال به‌روزرسانی اندازه‌ها…","Updating measurements…")}</p>}
      {status==="error"&&<Alert variant="destructive"><AlertDescription>{errorText}<Button variant="outline" size="sm" disabled={disabled} onClick={()=>setRetry(n=>n+1)}><RotateCcw data-icon="inline-start"/>{t("تلاش دوباره","Retry")}</Button></AlertDescription></Alert>}
      {matching&&<><dl className="geometry-measurements" aria-live="polite">{data.metrics.map(m=><div key={m.key}><dt>{labels[m.key][fa?0:1]}</dt><dd dir="ltr" data-testid={`geometry-${m.key}`}>{m.value===null?"—":number(m.value)}{m.unit==="degrees"?"°":m.unit==="radians"?" rad":""}</dd></div>)}</dl>
        {data.status!=="ok"&&<p className="block-note" role="status">{data.status==="degenerate"?t("این رأس‌ها مثلث غیرمنحط نمی‌سازند؛ زاویه‌های داخلی تعریف نشده‌اند.","These vertices do not form a nondegenerate triangle; interior angles are undefined."):t("زاویه با بردار صفر تعریف ندارد.","The angle with a zero vector is undefined.")}</p>}</>}
      {scene.kind==="unit_circle"?<FieldGroup><Field><div className="parameter-heading"><FieldLabel id={`${id}-angle`}>{t("زاویه بر حسب درجه","Angle in degrees")}</FieldLabel><output dir="ltr">{number(scene.angle_degrees)}°</output></div><Slider dir="ltr" value={[scene.angle_degrees]} min={0} max={360} step={1} disabled={disabled} aria-labelledby={`${id}-angle`} onValueChange={([value])=>update({...scene,angle_degrees:value})}/></Field></FieldGroup>:
        <details className="geometry-controls"><summary>{t("مختصات و کنترل نقاط","Point coordinates and controls")}</summary><FieldGroup>{controls.flatMap(p=>(["x","y"] as const).map(axis=><Field key={`${p.id}-${axis}`}><div className="parameter-heading"><FieldLabel id={`${id}-${p.id}-${axis}`}>{p.id}.{axis}</FieldLabel><output dir="ltr">{number(p[axis])}</output></div><Slider dir="ltr" value={[p[axis]]} min={-10} max={10} step={.1} disabled={disabled} aria-labelledby={`${id}-${p.id}-${axis}`} onValueChange={([value])=>update(moveGeometryPoint(scene,p.id,axis==="x"?value:p.x,axis==="y"?value:p.y))}/></Field>))}</FieldGroup></details>}
      <details className="graph-data"><summary>{t("توضیح متنی و مختصات","Text explanation and coordinates")}</summary><p>{block.fallback_text}</p><table dir="ltr"><thead><tr><th scope="col">{t("نقطه","Point")}</th><th scope="col">x</th><th scope="col">y</th></tr></thead><tbody>{data.points.map(p=><tr key={p.id}><th scope="row">{p.label}</th><td>{number(p.x)}</td><td>{number(p.y)}</td></tr>)}</tbody></table></details>
    </CardContent><CardFooter><Button variant="outline" size="sm" disabled={disabled} onClick={()=>change.current({kind:"geometry_canvas",scene:block.params.scene,geometry:block.params.geometry})}><RotateCcw data-icon="inline-start"/>{t("بازنشانی شکل","Reset diagram")}</Button>{onEvent && status==="error" && <Button variant="outline" disabled={disabled} onClick={()=>onEvent({type:"block_error",block_id:block.id,payload:{code:"geometry_failed"}})}>{t("ادامه با متن","Continue with text")}</Button>}<p className="block-note">{t("تغییر شکل، مرحله درس را جلو نمی‌برد.","Changing the diagram does not advance the lesson.")}</p></CardFooter>
  </Card>;
}
