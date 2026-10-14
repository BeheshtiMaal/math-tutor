import { z } from "zod";

const number=z.number().finite();
const coordinate=z.object({x:number.min(-10).max(10),y:number.min(-10).max(10)}).strict();
export const geometrySceneSchema=z.discriminatedUnion("kind",[
  z.object({kind:z.literal("unit_circle"),angle_degrees:number.min(0).max(360)}).strict(),
  z.object({kind:z.literal("triangle"),vertices:z.array(coordinate).length(3)}).strict(),
  z.object({kind:z.literal("vectors"),u:coordinate,v:coordinate}).strict(),
]);
const id=z.string().regex(/^[A-Za-z][A-Za-z0-9_]{0,11}$/);
const point=z.object({x:number.min(-20).max(20),y:number.min(-20).max(20)}).strict();
export const geometryResultSchema=z.object({
  status:z.enum(["ok","degenerate","zero_vector"]),scene:geometrySceneSchema,
  bounds:z.object({min:number,max:number}).strict().refine(b=>b.max>b.min && b.max-b.min<=200),
  points:z.array(point.extend({id,label:z.string().max(24).refine(s=>!/[<>`$#*]|https?:|javascript:|data:/i.test(s)),draggable:z.boolean()})).min(1).max(8),
  segments:z.array(z.object({start:id,end:id,style:z.enum(["edge","projection","vector"])}).strict()).max(12),
  circles:z.array(z.object({center:id,radius:number.positive().max(20)}).strict()).max(2),
  arcs:z.array(z.object({points:z.array(point).min(2).max(73)}).strict()).max(3),
  metrics:z.array(z.object({key:z.enum(["angle_deg","angle_rad","cos","sin","length_AB","length_BC","length_CA","angle_A","angle_B","angle_C","perimeter","area","length_u","length_v","length_sum","dot","between"]),
    value:number.min(-1_000_000).max(1_000_000).nullable(),unit:z.enum(["degrees","radians","length","area","scalar"])}).strict()).max(17),
}).strict().refine(data=>{
  const ids=new Set(data.points.map(p=>p.id));
  return ids.size===data.points.length && new Set(data.metrics.map(m=>m.key)).size===data.metrics.length &&
    data.segments.every(s=>ids.has(s.start)&&ids.has(s.end)) && data.circles.every(c=>ids.has(c.center)) &&
    data.points.every(p=>p.x>=data.bounds.min&&p.x<=data.bounds.max&&p.y>=data.bounds.min&&p.y<=data.bounds.max);
});
export const geometryParamsSchema=z.object({scene:geometrySceneSchema,language:z.enum(["fa","en"]),geometry:geometryResultSchema}).strict()
  .refine(params=>sameScene(params.scene,params.geometry.scene));
export type GeometryScene=z.infer<typeof geometrySceneSchema>;
export type GeometryResult=z.infer<typeof geometryResultSchema>;
export type GeometryState={kind:"geometry_canvas";scene:GeometryScene;geometry?:GeometryResult};
export function sameScene(a:GeometryScene,b:GeometryScene){return JSON.stringify(a)===JSON.stringify(b);}
export function sceneFor(initial:GeometryScene,saved?:{kind:string;scene?:unknown}):GeometryScene {
  const parsed=saved?.kind==="geometry_canvas" ? geometrySceneSchema.safeParse(saved.scene):null;
  return parsed?.success && parsed.data.kind===initial.kind ? parsed.data:initial;
}
export function moveGeometryPoint(scene:GeometryScene,id:string,x:number,y:number):GeometryScene {
  x=Math.round(Math.max(-10,Math.min(10,x))*10)/10;
  y=Math.round(Math.max(-10,Math.min(10,y))*10)/10;
  if(scene.kind==="triangle")return {...scene,vertices:scene.vertices.map((p,i)=>"ABC"[i]===id?{x,y}:p)};
  if(scene.kind==="vectors")return id==="U"?{...scene,u:{x,y}}:id==="V"?{...scene,v:{x,y}}:scene;
  const angle=(Math.atan2(y,x)*180/Math.PI+360)%360;
  return {...scene,angle_degrees:Math.round(angle)};
}
