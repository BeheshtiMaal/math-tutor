import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {emptyProfile,rememberTopic,correctLevel,automaticLevel,parseProfile,trimProfile} from "@/lib/learner-profile";
import {loadLearnerProfile,saveLearnerProfile,rememberLearnerTurn,resetLearnerProfile,saveChat,loadChats,deleteChat} from "@/lib/storage";
import {newChat} from "@/lib/contracts";
import {LearnerMemory} from "@/components/learner-memory";
afterEach(cleanup);

it("keeps manual corrections while counting repeated confusion and preserves weak points on automatic selection",()=>{
  let profile=rememberTopic(emptyProfile(),"logarithms","beginner","inferred",{concept:"پایه",step_id:"s1"});
  profile=correctLevel(profile,"logarithms","advanced");
  profile=rememberTopic(profile,"logarithms","beginner","inferred",{concept:"پایه",step_id:"s1"});
  expect(profile.topics.logarithms.level).toBe("advanced");expect(profile.topics.logarithms.level_source).toBe("manual");
  expect(profile.topics.logarithms.confusion_spots[0].count).toBe(2);
  profile=automaticLevel(profile,"logarithms");
  expect(profile.topics.logarithms.level_source).toBe("inferred");expect(profile.topics.logarithms.confusion_spots[0].count).toBe(2);
});

it("bounds topics, weak points, recent topics and UTF8 payload while keeping the active topic",()=>{
  let profile=emptyProfile();
  for(let topic=0;topic<55;topic++)for(let spot=0;spot<12;spot++)profile=rememberTopic(profile,`topic${topic}`,"beginner","inferred",{concept:`${spot}${"ژ".repeat(119)}`});
  const trimmed=trimProfile(profile,"topic54");
  expect(Object.keys(trimmed.topics).length).toBeLessThanOrEqual(50);
  expect(trimmed.topics.topic54.confusion_spots).toHaveLength(10);
  expect(trimmed.recent_topics.length).toBeLessThanOrEqual(20);
  expect(new TextEncoder().encode(JSON.stringify(trimmed)).length).toBeLessThanOrEqual(15000);
});

it("drops malformed profiles, ignores unknown fields and clamps future timestamps",()=>{
  expect(parseProfile({version:99,topics:{}})).toEqual(emptyProfile());
  const profile=rememberTopic(emptyProfile(),"algebra","beginner","inferred");
  const parsed=parseProfile({...profile,extra:"ignored",updated_at:"2099-01-01T00:00:00Z"});
  expect(parsed).not.toHaveProperty("extra");expect(Date.parse(parsed.updated_at!)).toBeLessThanOrEqual(Date.now());
});

it("persists accepted turns once and reset removes profile snapshots without deleting chats",async()=>{
  await resetLearnerProfile();
  const startedAt=Date.now()+1;
  const turn={id:"profile-test-1",startedAt,topic:"algebra",level:"beginner" as const,source:"inferred" as const,spot:{concept:"تجزیه"}};
  await rememberLearnerTurn(turn);await rememberLearnerTurn(turn);
  const profile=await loadLearnerProfile();expect(profile.topics.algebra.confusion_spots[0].count).toBe(1);
  const chat=newChat();chat.messages=[{id:"history",role:"user",segments:[{kind:"text",text:"پرسش محفوظ"}]}];
  chat.pending={requestId:"retry",messageId:"reply",request:{thread_id:chat.threadId,message:"",action:"simplify",mode:"learn",delivery:"step",learner_profile:profile}};
  await saveChat(chat);
  await resetLearnerProfile();
  expect((await loadLearnerProfile()).topics).toEqual({});
  const saved=(await loadChats()).find(item=>item.id===chat.id)!;
  expect(saved.pending?.request).not.toHaveProperty("learner_profile");expect(saved.pending?.requestId).toBe("retry");
  expect(saved.messages).toEqual(chat.messages);
  await rememberLearnerTurn({...turn,id:"old-turn",startedAt:0});expect((await loadLearnerProfile()).topics).toEqual({});
  await deleteChat(chat.id);
});

it("manual topic choices survive a reload of the profile store",async()=>{
  await resetLearnerProfile();
  await saveLearnerProfile(correctLevel(emptyProfile(),"logarithms","intermediate"));
  expect((await loadLearnerProfile()).topics.logarithms.level_source).toBe("manual");
  expect((await loadLearnerProfile()).topics.logarithms.level).toBe("intermediate");
  await resetLearnerProfile();
});

it("shows the heuristic limitation and an accessible profile reset control",async()=>{
  const reset=vi.fn().mockResolvedValue(undefined);
  render(<LearnerMemory profile={rememberTopic(emptyProfile(),"algebra","beginner","inferred")} disabled={false} onCorrect={vi.fn()} onReset={reset}/>);
  fireEvent.click(screen.getByRole("button",{name:"حافظه یادگیری"}));
  expect(screen.getByRole("dialog")).toBeVisible();
  expect(screen.getByText(/آزمون مهارت نیست/)).toBeVisible();
  fireEvent.click(screen.getByRole("button",{name:"پاک کردن حافظه"}));
  await waitFor(()=>expect(reset).toHaveBeenCalledTimes(1));
  await waitFor(()=>expect(screen.getByRole("status")).toHaveTextContent("حافظه پاک شد"));
});
