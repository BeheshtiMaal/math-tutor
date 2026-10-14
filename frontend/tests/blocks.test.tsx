import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BlockRenderer } from "@/components/blocks/block-renderer";
import { blockSchema, curvePaths, type BlockState, type GraphBlock, type StepBlock } from "@/lib/ui-blocks";
import fixtures from "./fixtures/blocks.json";
import { newChat } from "@/lib/contracts";
import { loadChats, saveChat, deleteChat } from "@/lib/storage";
const graph=blockSchema.parse(fixtures.graph) as GraphBlock, steps=blockSchema.parse(fixtures.steps) as StepBlock;
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});

function Demo({payload=graph,state:initial}:{payload?:unknown;state?:BlockState}) {
  const [state,setState]=useState(initial);
  return <BlockRenderer entry={{id:"demo",payload,state}} threadId="thr_00000000000000000000000000" onChange={setState} onAsk={vi.fn()}/>;
}

it("splits a curve at an undefined interval and a pole between samples",()=>{
  const project=(x:number,y:number):[number,number]=>[x,y];
  const points=[{x:-1,y:-1},{x:1,y:1},{x:2,y:0.5}];
  expect(curvePaths(points,[{from:0,to:0}],project)).toHaveLength(2);
  expect(curvePaths(points,[{from:-0.5,to:1.5}],project)).toHaveLength(2);
});

for(const theme of ["light","dark"]) it(`renders graph data, LTR math and keyboard controls in ${theme}`,()=>{
  document.documentElement.dataset.theme=theme;
  const {container}=render(<Demo/>);
  expect(screen.getByRole("img",{name:/Logarithm graph/})).toBeInTheDocument();
  expect(screen.getByRole("slider",{name:/پارامتر b/})).toHaveAttribute("aria-valuenow","2");
  expect(container.querySelectorAll("[data-testid=curve-path]").length).toBeGreaterThan(0);
  expect(container.querySelector(".plot-gap")).toBeInTheDocument();
  expect(screen.getByTestId("graph-highlight").textContent).toContain("3");
  expect(screen.getByText("توضیح متنی و داده‌های نمودار")).toBeInTheDocument();
});

it("debounces slider changes and accepts only the current sampling result",async()=>{
  let resolveFirst:(value:Response)=>void=()=>{};
  const fetcher=vi.fn().mockImplementationOnce(()=>new Promise<Response>(resolve=>resolveFirst=resolve)).mockResolvedValueOnce(new Response(JSON.stringify(graph.params.samples),{status:200}));
  vi.stubGlobal("fetch",fetcher);
  render(<Demo/>);
  fireEvent.keyDown(screen.getByRole("slider"),{key:"ArrowRight"});
  await waitFor(()=>expect(fetcher).toHaveBeenCalledTimes(1));
  const firstSignal=fetcher.mock.calls[0][1].signal as AbortSignal;
  fireEvent.keyDown(screen.getByRole("slider"),{key:"ArrowRight"});
  expect(firstSignal.aborted).toBe(true);
  await waitFor(()=>expect(fetcher).toHaveBeenCalledTimes(2));
  expect(JSON.parse(fetcher.mock.calls[1][1].body).parameters.b).toBe(2.2);
  resolveFirst(new Response(JSON.stringify({status:"invalid_expression",series:[],highlight_points:[],domain_warnings:[]})));
  await waitFor(()=>expect(screen.queryByText(/این مقادیر برای تابع/)).not.toBeInTheDocument());
  expect(screen.getByTestId("value-b")).toHaveTextContent("2.2");
});

it("shows sampling failures and retries without requesting a chat turn",async()=>{
  const fetcher=vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(new Response(JSON.stringify(graph.params.samples),{status:200}));
  vi.stubGlobal("fetch",fetcher);
  render(<Demo state={{kind:"function_graph",parameters:{b:0.5}}}/>);
  await waitFor(()=>expect(screen.getByRole("button",{name:"تلاش دوباره برای نمودار"})).toBeVisible());
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button",{name:"تلاش دوباره برای نمودار"}));
  await waitFor(()=>expect(screen.getByRole("img")).toBeInTheDocument());
  expect(fetcher.mock.calls.every(([url])=>url==="/api/ui/sample")).toBe(true);
});

for(const theme of ["light","dark"]) it(`reveals steps, highlights changed math and labels unchecked rows in ${theme}`,()=>{
  document.documentElement.dataset.theme=theme;
  const modified=structuredClone(steps);modified.params.steps[1].verification="unknown";
  const {container}=render(<Demo payload={modified}/>);
  expect(screen.getByText("مرحلهٔ ۱ از ۳")).toBeInTheDocument();
  expect(screen.getByRole("button",{name:"مرحلهٔ قبل"})).toBeDisabled();
  fireEvent.click(screen.getByRole("button",{name:"مرحلهٔ بعد"}));
  expect(screen.getByText("مرحلهٔ ۲ از ۳")).toBeInTheDocument();
  expect(screen.getByText("بررسی ماشینی نشده")).toBeInTheDocument();
  expect(container.querySelector(".changed-math .katex")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button",{name:"مرحلهٔ قبل"}));
  expect(screen.getByText("مرحلهٔ ۱ از ۳")).toBeInTheDocument();
});

it("prepares an explicit current-step question without sending a UI event",()=>{
  const onAsk=vi.fn(),onChange=vi.fn();
  render(<BlockRenderer entry={{id:"ask",payload:steps,state:{kind:"step_reveal",index:1}}} threadId="thread" onAsk={onAsk} onChange={onChange}/>);
  fireEvent.click(screen.getByRole("button",{name:"این مرحله را نفهمیدم"}));
  expect(onAsk).toHaveBeenCalledWith(expect.stringContaining(steps.params.steps[1].state));
  expect(onChange).not.toHaveBeenCalled();
  expect(screen.getByText(/پرسش این مرحله در کادر پیام/)).toBeInTheDocument();
});

it("degrades unknown versions, hostile and invalid payloads to escaped text",()=>{
  const warn=vi.spyOn(console,"warn").mockImplementation(()=>{});
  for(const payload of [{...graph,version:9},{...graph,type:"new_kind"},{...graph,params:{}},{...graph,fallback_text:"<script>alert(1)</script>",type:"unknown"}]) {
    const {container,unmount}=render(<Demo payload={payload}/>);
    expect(container.querySelector(".block-fallback")).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();unmount();
  }
  expect(warn).toHaveBeenCalled();
});

it("isolates a plotting failure while a neighboring step block still works",()=>{
  vi.spyOn(console,"error").mockImplementation(()=>{});vi.spyOn(console,"warn").mockImplementation(()=>{});
  const broken=structuredClone(graph);broken.params.samples.series[0].points.forEach((point,i)=>point.y=i%2 ? 1e308:-1e308);
  const {container}=render(<><Demo payload={broken}/><Demo payload={steps}/></>);
  expect(container.querySelector(".block-fallback")).toHaveTextContent(graph.fallback_text);
  fireEvent.click(screen.getByRole("button",{name:"مرحلهٔ بعد"}));
  expect(screen.getByText("مرحلهٔ ۲ از ۳")).toBeInTheDocument();
});

it("persists slider samples and step position with the existing chat schema",async()=>{
  const chat=newChat();chat.messages=[{id:"visuals",role:"assistant",segments:[],blocks:[{id:graph.id,payload:graph,state:{kind:"function_graph",parameters:{b:2},samples:graph.params.samples,sampledParameters:{b:2}}},{id:steps.id,payload:steps,state:{kind:"step_reveal",index:2}}]}];
  await saveChat(chat);const restored=(await loadChats()).find(item=>item.id===chat.id)!;
  expect(restored.messages[0].blocks?.[0].state).toMatchObject({parameters:{b:2}});
  expect(restored.messages[0].blocks?.[1].state).toMatchObject({index:2});await deleteChat(chat.id);
});
