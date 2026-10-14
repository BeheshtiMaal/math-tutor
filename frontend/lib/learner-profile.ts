import {z} from "zod";
import type {Level} from "./contracts";

export const levelSchema=z.enum(["beginner","intermediate","advanced"]);
const timestamp=z.string().datetime({offset:true}).transform(value=>{
  const time=Date.parse(value);return new Date(time>Date.now()+300000?Date.now():time).toISOString();
});
const confusion=z.object({concept:z.string().trim().min(1).max(120),step_id:z.string().max(120).nullable().default(null),count:z.number().int().min(1).max(1000),last_seen:timestamp.nullable().default(null)});
const topic=z.object({level:levelSchema,level_source:z.enum(["manual","inferred"]),confusion_spots:z.array(confusion).max(10).default([]),last_seen:timestamp.nullable().default(null)});
export const profileSchema=z.object({version:z.literal(1),topics:z.record(z.string().min(1).max(128),topic),recent_topics:z.array(z.string().max(120)).max(20),updated_at:timestamp.nullable().default(null)})
  .refine(value=>Object.keys(value.topics).length<=50&&new TextEncoder().encode(JSON.stringify(value)).length<=16384);
export type LearnerProfile=z.infer<typeof profileSchema>;
export type Confusion=z.infer<typeof confusion>;
export const emptyProfile=():LearnerProfile=>({version:1,topics:{},recent_topics:[],updated_at:null});
export function parseProfile(value:unknown):LearnerProfile {const parsed=profileSchema.safeParse(value);return parsed.success?parsed.data:emptyProfile();}
export function topicEntry(profile:LearnerProfile,key?:string) {return key&&Object.hasOwn(profile.topics,key)?profile.topics[key]:undefined;}

export function trimProfile(profile:LearnerProfile,preferred?:string):LearnerProfile {
  const rows=Object.entries(profile.topics).sort(([a,x],[b,y])=>a===preferred?-1:b===preferred?1:Date.parse(y.last_seen||"")-Date.parse(x.last_seen||""));
  let result: LearnerProfile={version:1,topics:Object.fromEntries(rows.slice(0,50)),recent_topics:profile.recent_topics.filter(key=>key.length<=120).slice(0,20),updated_at:profile.updated_at};
  for(const [key,entry] of Object.entries(result.topics))result.topics[key]={...entry,confusion_spots:entry.confusion_spots.slice(0,10)};
  while(new TextEncoder().encode(JSON.stringify(result)).length>15000&&Object.keys(result.topics).length){
    const kept=Object.entries(result.topics);kept.pop();result={...result,topics:Object.fromEntries(kept)};
  }
  result.recent_topics=result.recent_topics.filter(key=>Object.hasOwn(result.topics,key));
  return parseProfile(result);
}

export function rememberTopic(profile:LearnerProfile,key:string,level:Level,source:"manual"|"inferred",spot?:{concept:string;step_id?:string},now=new Date().toISOString()):LearnerProfile {
  if(!key||key.length>128)return profile;
  const before=topicEntry(profile,key),manual=before?.level_source==="manual"&&source!=="manual";
  let spots=[...(before?.confusion_spots||[])];
  if(spot){
    const concept=spot.concept.trim().slice(0,120)||key;
    const previous=spots.find(item=>item.concept===concept&&item.step_id===(spot.step_id||null));
    spots=[{concept,step_id:spot.step_id?.slice(0,120)||null,count:Math.min(1000,(previous?.count||0)+1),last_seen:now},...spots.filter(item=>item!==previous)].slice(0,10);
  }
  const entry={level:manual?before.level:level,level_source:manual?"manual" as const:source,confusion_spots:spots,last_seen:now};
  return trimProfile({version:1,topics:{...profile.topics,[key]:entry},recent_topics:[key,...profile.recent_topics.filter(item=>item!==key)].slice(0,20),updated_at:now},key);
}

export function correctLevel(profile:LearnerProfile,key:string,level:Level):LearnerProfile {return rememberTopic(profile,key,level,"manual");}
export function automaticLevel(profile:LearnerProfile,key:string):LearnerProfile {
  const before=topicEntry(profile,key);
  if(!before)return profile;
  return trimProfile({...profile,topics:{...profile.topics,[key]:{...before,level:"beginner",level_source:"inferred"}},updated_at:new Date().toISOString()});
}
