"use client";
import { Component, useEffect, useMemo, useRef, type ReactNode } from "react";
import { FunctionGraph } from "./function-graph";
import { StepReveal } from "./step-reveal";
import { GeometryCanvas } from "./geometry-canvas";
import { blockSchema, fallbackFor, type StoredBlock, type BlockState } from "@/lib/ui-blocks";
import type { EventIntent, LocalEventIntent } from "@/lib/ui-events";
import { Button } from "@/components/ui/button";

class BlockBoundary extends Component<{children:ReactNode;fallback:ReactNode},{broken:boolean}> {
  state={broken:false};
  static getDerivedStateFromError(){return {broken:true};}
  componentDidCatch(){console.warn("MathTutor block diagnostic: render_failed");}
  render(){return this.state.broken ? this.props.fallback : this.props.children;}
}

export function BlockRenderer({entry,threadId,onChange,onAsk,onEvent,onLocalEvent,disabled=false}:{entry:StoredBlock;threadId:string;onChange:(state:BlockState)=>void;onAsk:(question:string)=>void;onEvent?:(event:EventIntent)=>void;onLocalEvent?:(event:LocalEventIntent)=>void;disabled?:boolean}) {
  const parsed=useMemo(()=>blockSchema.safeParse(entry.payload),[entry.payload]);
  const viewRecorded=useRef(false),local=useRef(onLocalEvent);local.current=onLocalEvent;
  useEffect(()=>{if(!disabled && !viewRecorded.current){viewRecorded.current=true;local.current?.({type:"block_view",block_id:entry.id,payload:{}});}},[entry.id,disabled]);
  useEffect(()=>{if(!parsed.success)console.warn("MathTutor block diagnostic: unsupported_or_invalid");},[parsed.success]);
  const fallback=<div className="block-fallback" dir="auto"><p>{fallbackFor(entry.payload)}</p>{onEvent && <Button variant="outline" disabled={disabled} onClick={()=>onEvent({type:"block_error",block_id:entry.id,payload:{code:"render_failed"}})}>ادامه با متن</Button>}</div>;
  if(!parsed.success) return fallback;
  const block=parsed.data;
  const change=(state:BlockState)=>{
    if(state.kind==="function_graph" && JSON.stringify(state.parameters)!==JSON.stringify(entry.state?.kind==="function_graph"?entry.state.parameters:undefined))onLocalEvent?.({type:"graph_slider",block_id:block.id,payload:{params:state.parameters}});
    if(state.kind==="step_reveal" && block.type==="step_reveal"){
      const before=entry.state?.kind==="step_reveal" ? entry.state.index : 0;
      if(state.index!==before)onLocalEvent?.({type:state.index>before?"step_next":"step_prev",block_id:block.id,payload:{step_id:block.params.steps[state.index].step_id}});
    }
    onChange(state);
  };
  // Closed renderer registry, keyed by type + version. No generated code or
  // model-selected module names are executed.
  const registry = {
    "function_graph:1":()=>block.type==="function_graph" ? <FunctionGraph block={block} threadId={threadId} state={entry.state} onChange={change} onEvent={onEvent} disabled={disabled}/> : null,
    "step_reveal:1":()=>block.type==="step_reveal" ? <StepReveal block={block} state={entry.state} onChange={change} onAsk={onAsk} onEvent={onEvent} disabled={disabled}/> : null,
    "geometry_canvas:1":()=>block.type==="geometry_canvas" ? <GeometryCanvas block={block} threadId={threadId} state={entry.state} onChange={change} onEvent={onEvent} disabled={disabled}/> : null,
  };
  return <BlockBoundary key={entry.id} fallback={fallback}>{registry[`${block.type}:${block.version}`]()}</BlockBoundary>;
}
