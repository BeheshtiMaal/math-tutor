import {threadId} from "./contracts";
export type EventIntent =
  | {type:"step_confused";block_id:string;payload:{step_id:string}}
  | {type:"graph_question";block_id:string;payload:{params:Record<string,number>}}
  | {type:"block_error";block_id:string;payload:{code:string}};
export type UIEvent = EventIntent & {event_id:string;thread_id:string;seq:number;sent_at:string};
export type LocalEventIntent = {type:"step_next"|"step_prev";block_id:string;payload:{step_id:string}} | {type:"graph_slider";block_id:string;payload:{params:Record<string,number>}} | {type:"block_view";block_id:string;payload:Record<string,never>};
export type LocalEvent = LocalEventIntent & {seq:number;sent_at:string};
export function createUIEvent(intent:EventIntent,thread:string,seq:number):UIEvent {
  return {...intent,event_id:threadId().replace("thr_","evt_"),thread_id:thread,seq,sent_at:new Date().toISOString()};
}
export function describeEvent(intent:EventIntent,fa=true):string {
  if(intent.type==="step_confused")return fa ? "این مرحله را ساده‌تر توضیح بده." : "Explain this step more simply.";
  if(intent.type==="block_error")return fa ? "این بخش نمایش داده نشد؛ با متن ادامه بده." : "This component could not be displayed; continue with text.";
  const values=Object.entries(intent.payload.params).map(([key,value])=>`$${key} = ${value}$`).join(", ");
  return fa ? `دربارهٔ این نمودار توضیح بده${values ? `: ${values}` : "."}` : `Explain this graph${values ? `: ${values}` : "."}`;
}
export class EventRateLimit {
  private times=new Map<string,number[]>();
  allow(thread:string,now=Date.now()) {
    const recent=(this.times.get(thread)||[]).filter(time=>now-time<5000);
    if(recent.length>=5)return false;
    this.times.set(thread,[...recent,now]);return true;
  }
}
