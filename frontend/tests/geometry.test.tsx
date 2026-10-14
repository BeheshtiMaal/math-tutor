import {useState} from "react";
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {BlockRenderer} from "@/components/blocks/block-renderer";
import {blockSchema,type BlockState,type GeometryBlock} from "@/lib/ui-blocks";
import {geometryResultSchema,moveGeometryPoint} from "@/lib/geometry";
import fixtures from "./fixtures/geometry.json";

const blocks=Object.fromEntries(["circle","triangle","vectors"].map(key=>[key,blockSchema.parse(fixtures[key as keyof typeof fixtures])])) as Record<string,GeometryBlock>;
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
function Demo({block=blocks.circle,initial}:{block?:GeometryBlock;initial?:BlockState}){
  const [state,setState]=useState(initial);
  return <BlockRenderer entry={{id:block.id,payload:block,state}} threadId="thr_00000000000000000000000000" onChange={setState} onAsk={vi.fn()}/>;
}

for(const kind of ["circle","triangle","vectors"])it(`renders ${kind} with measurements and text/keyboard alternatives`,()=>{
  const {container}=render(<Demo block={blocks[kind]}/>);
  expect(screen.getByRole("region",{name:blocks[kind].title})).toBeInTheDocument();
  expect(container.querySelector("svg")).toBeInTheDocument();
  expect(container.querySelectorAll(".geometry-measurements dd").length).toBeGreaterThan(0);
  expect(screen.getByText("توضیح متنی و مختصات")).toBeInTheDocument();
  if(kind==="triangle"){expect(screen.getByTestId("geometry-area").textContent).toBe("6");expect(screen.getByTestId("geometry-angle_A").textContent).toBe("90°");}
  if(kind==="vectors")expect(screen.getByTestId("geometry-length_sum").textContent).toBe("5");
});

it("updates a focused point without advancing chat and ignores stale geometry replies",async()=>{
  let resolveFirst:(value:Response)=>void=()=>{};
  const fetcher=vi.fn().mockImplementationOnce(()=>new Promise<Response>(resolve=>resolveFirst=resolve)).mockResolvedValueOnce(new Response(JSON.stringify(fixtures.circle47),{status:200}));
  vi.stubGlobal("fetch",fetcher);render(<Demo/>);
  const point=screen.getByRole("button",{name:"جابه‌جایی نقطه P"});
  fireEvent.keyDown(point,{key:"ArrowRight"});
  await waitFor(()=>expect(fetcher).toHaveBeenCalledTimes(1));
  const firstSignal=fetcher.mock.calls[0][1].signal as AbortSignal;
  fireEvent.keyDown(point,{key:"ArrowRight"});
  await waitFor(()=>expect(fetcher).toHaveBeenCalledTimes(2));
  expect(firstSignal.aborted).toBe(true);
  expect(JSON.parse(fetcher.mock.calls[1][1].body).scene.angle_degrees).toBe(47);
  resolveFirst(new Response(JSON.stringify(fixtures.circle46),{status:200}));
  await waitFor(()=>expect(screen.getByTestId("geometry-angle_deg").textContent).toBe("47°"));
  expect(fetcher.mock.calls.every(call=>call[0]==="/api/ui/geometry")).toBe(true);
});

it("restores saved scene and measurements without a network call and resets locally",()=>{
  const fetcher=vi.fn();vi.stubGlobal("fetch",fetcher);
  const data=geometryResultSchema.parse(fixtures.circle90);
  render(<Demo initial={{kind:"geometry_canvas",scene:data.scene,geometry:data}}/>);
  expect(screen.getByTestId("geometry-angle_deg").textContent).toBe("90°");
  fireEvent.click(screen.getByRole("button",{name:"بازنشانی شکل"}));
  expect(screen.getByTestId("geometry-angle_deg").textContent).toBe("45°");
  expect(fetcher).not.toHaveBeenCalled();
});

it("rejects hostile scenes, forged scene/result pairs and missing references",()=>{
  const bad=structuredClone(fixtures.circle);(bad.params.scene as unknown as Record<string,unknown>).script="alert(1)";
  expect(blockSchema.safeParse(bad).success).toBe(false);
  const mismatched=structuredClone(fixtures.circle);mismatched.params.geometry=fixtures.circle90;
  expect(blockSchema.safeParse(mismatched).success).toBe(false);
  const reference=structuredClone(fixtures.circle);reference.params.geometry.segments[0].end="unknown";
  expect(blockSchema.safeParse(reference).success).toBe(false);
  expect(moveGeometryPoint(blocks.triangle.params.scene,"A",999,-999)).toMatchObject({vertices:[{x:10,y:-10},{x:4,y:0},{x:0,y:3}]});
});

it("shows an honest degenerate-triangle explanation",()=>{
  const data=geometryResultSchema.parse(fixtures.degenerate);
  render(<Demo block={blocks.triangle} initial={{kind:"geometry_canvas",scene:data.scene,geometry:data}}/>);
  expect(screen.getByText(/این رأس‌ها مثلث غیرمنحط/)).toBeInTheDocument();
  expect(screen.getByTestId("geometry-angle_A").textContent).toBe("—°");
});
