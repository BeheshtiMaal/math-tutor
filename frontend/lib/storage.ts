import { openDB, type DBSchema, type IDBPDatabase } from "idb";
import type { Chat } from "./contracts";
import {emptyProfile,parseProfile,trimProfile,rememberTopic,type LearnerProfile} from "./learner-profile";
import type {Level} from "./contracts";
interface TutorDB extends DBSchema {
  chats: {key: string; value: Chat};
  settings: {key: string; value: string};
}
let connection: Promise<IDBPDatabase<TutorDB>> | null = null;
const database = () => connection ??= openDB<TutorDB>("mathtutor", 1, {
  upgrade(db) { db.createObjectStore("chats", {keyPath: "id"}); db.createObjectStore("settings"); },
  blocked() { window.dispatchEvent(new Event("tutor-storage-blocked")); },
  blocking() { void connection?.then(db => db.close()); connection = null; },
  terminated() { connection = null; },
}).catch(error => { connection = null; throw error; });
export async function loadChats() { const db = await database(); return (await db.getAll("chats")).sort((a,b) => b.updatedAt-a.updatedAt); }
export async function saveChat(chat: Chat) { const db = await database(); await db.put("chats", chat); }
export async function deleteChat(id: string) { const db = await database(); await db.delete("chats", id); }
export async function getSetting(key: string) { const db = await database(); return db.get("settings", key); }
export async function setSetting(key: string, value: string) { const db = await database(); await db.put("settings", value, key); }
const PROFILE_KEY="learner-profile",TURN_IDS="profile-turns",RESET_AT="profile-reset-at";
function decoded(raw?:string):LearnerProfile {try{return parseProfile(JSON.parse(raw||"null"));}catch{return emptyProfile();}}
export async function loadLearnerProfile(){return decoded(await getSetting(PROFILE_KEY));}
export async function saveLearnerProfile(profile:LearnerProfile){await setSetting(PROFILE_KEY,JSON.stringify(trimProfile(profile)));}
export async function rememberLearnerTurn({id,startedAt,topic,level,source,spot}:{id:string;startedAt:number;topic:string;level:Level;source:"manual"|"inferred";spot?:{concept:string;step_id?:string}}){
  const db=await database(),tx=db.transaction("settings","readwrite"),store=tx.objectStore("settings");
  const profile=decoded(await store.get(PROFILE_KEY));
  let ids:string[]=[];try{const raw=JSON.parse(await store.get(TURN_IDS)||"[]");if(Array.isArray(raw))ids=raw.filter((id:unknown)=>typeof id==="string").slice(-128);}catch{}
  const reset=Number(await store.get(RESET_AT)||0);
  if(ids.includes(id)||startedAt<reset){await tx.done;return profile;}
  const next=rememberTopic(profile,topic,level,source,spot);
  await store.put(JSON.stringify(next),PROFILE_KEY);await store.put(JSON.stringify([...ids,id].slice(-128)),TURN_IDS);await tx.done;
  return next;
}
export async function resetLearnerProfile(){
  const db=await database(),tx=db.transaction(["settings","chats"],"readwrite");
  await tx.objectStore("settings").put(JSON.stringify(emptyProfile()),PROFILE_KEY);
  await tx.objectStore("settings").put("[]",TURN_IDS);
  await tx.objectStore("settings").put(String(Date.now()),RESET_AT);
  for(const chat of await tx.objectStore("chats").getAll())if(chat.pending?.request.learner_profile){
    const {learner_profile,...request}=chat.pending.request;
    await tx.objectStore("chats").put({...chat,pending:{...chat.pending,request}});
  }
  await tx.done;return emptyProfile();
}
export function exportChats(chats: Chat[]) {
  const url = URL.createObjectURL(new Blob([JSON.stringify({version: 1, exportedAt: new Date().toISOString(), chats}, null, 2)], {type: "application/json"}));
  const a = document.createElement("a"); a.href = url; a.download = "mathtutor-chats.json"; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
