import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {BlockRenderer} from "@/components/blocks/block-renderer";
import {blockSchema,type StepBlock} from "@/lib/ui-blocks";
import {createUIEvent,describeEvent,EventRateLimit} from "@/lib/ui-events";
import fixtures from "./fixtures/blocks.json";
afterEach(cleanup);

it("sends the selected issued step ID rather than math from the browser",()=>{
  const steps=blockSchema.parse(fixtures.steps) as StepBlock,event=vi.fn(),ask=vi.fn(),local=vi.fn();
  render(<BlockRenderer entry={{id:steps.id,payload:steps,state:{kind:"step_reveal",index:1}}} threadId={"thr_"+"0".repeat(26)} onChange={vi.fn()} onAsk={ask} onEvent={event} onLocalEvent={local}/>);
  fireEvent.click(screen.getByRole("button",{name:"این مرحله را نفهمیدم"}));
  expect(event).toHaveBeenCalledWith({type:"step_confused",block_id:steps.id,payload:{step_id:steps.params.steps[1].step_id}});
  expect(ask).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button",{name:"مرحلهٔ بعد"}));
  expect(event).toHaveBeenCalledTimes(1);
  expect(local).toHaveBeenLastCalledWith({type:"step_next",block_id:steps.id,payload:{step_id:steps.params.steps[2].step_id}});
});

it("asks about current graph parameters only on explicit click",()=>{
  const graph=blockSchema.parse(fixtures.graph),event=vi.fn();
  render(<BlockRenderer entry={{id:graph.id,payload:graph}} threadId={"thr_"+"0".repeat(26)} onChange={vi.fn()} onAsk={vi.fn()} onEvent={event}/>);
  expect(event).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button",{name:"دربارهٔ این نمودار بپرس"}));
  expect(event).toHaveBeenCalledWith({type:"graph_question",block_id:graph.id,payload:{params:{b:2}}});
});

it("has a text continuation for unsupported blocks and obeys disabled state",()=>{
  const event=vi.fn();
  const props={entry:{id:fixtures.graph.id,payload:{...fixtures.graph,version:99}},threadId:"thr_"+"0".repeat(26),onChange:vi.fn(),onAsk:vi.fn(),onEvent:event};
  const {rerender}=render(<BlockRenderer {...props} disabled/>);
  expect(screen.getByRole("button",{name:"ادامه با متن"})).toBeDisabled();
  rerender(<BlockRenderer {...props}/>);fireEvent.click(screen.getByRole("button",{name:"ادامه با متن"}));
  expect(event).toHaveBeenCalledWith({type:"block_error",block_id:fixtures.graph.id,payload:{code:"render_failed"}});
});

it("creates bounded IDs, preserves parameters and gives a transparent description",()=>{
  const intent={type:"graph_question" as const,block_id:fixtures.graph.id,payload:{params:{b:.5}}};
  const event=createUIEvent(intent,"thr_"+"0".repeat(26),12);
  expect(event.event_id).toMatch(/^evt_[0-7][0-9A-HJKMNP-TV-Z]{25}$/);
  expect(event.seq).toBe(12);expect(event.sent_at).toMatch(/Z$/);
  expect(describeEvent(intent)).toContain("b = 0.5");expect(describeEvent(intent,false)).toContain("Explain this graph");
});

it("limits five events per five seconds independently for each thread",()=>{
  const limiter=new EventRateLimit();
  for(let i=0;i<5;i++)expect(limiter.allow("one",100+i)).toBe(true);
  expect(limiter.allow("one",200)).toBe(false);expect(limiter.allow("two",200)).toBe(true);
  expect(limiter.allow("one",5100)).toBe(true);
});
