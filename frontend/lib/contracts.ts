export type Level = "beginner" | "intermediate" | "advanced";
export type Action = "new_lesson" | "followup" | "next" | "simplify" | "full" | "done" | "ui_event";
export type Segment = {kind: "text" | "answer"; text: string};
export type Lesson = {step_index: number; total_steps: number; awaiting_user: boolean; can_continue: boolean;concept?:string|null};
export type TurnRequest = {thread_id: string; message: string; action: Action; mode: "learn" | "answer"; delivery: "full" | "step"; level?:Level; level_source?:"manual"|"inferred";learner_profile?:import("./learner-profile").LearnerProfile;ui_event?:import("./ui-events").UIEvent};
import type { StoredBlock } from "./ui-blocks";
export type Message = {id: string; role: "user" | "assistant" | "system"; segments: Segment[]; partial?: boolean; blocks?: StoredBlock[]};
export type PendingTurn = {request: TurnRequest; requestId: string; messageId: string;startedAt?:number};
export type Chat = {id: string; threadId: string; title: string; updatedAt: number; messages: Message[]; level: Level;manualLevel?:Level;levelSource?:"manual"|"inferred"|"default";levelSuggestion?:Level|null; delivery: "full" | "step"; mode: "learn" | "answer"; lesson?: Lesson; topic?: string; expired?: boolean; pending?: PendingTurn;eventSeq?:number;language?:string;uiHistory?:import("./ui-events").LocalEvent[]};
export type EndEvent = {thread_id: string; turn_id: string; awaiting_user: boolean; status?: string; lesson: Lesson | null; topic?: string; language?: string;mode?:"learn"|"answer";learner_level?:Level;level_source?:"manual"|"inferred"|"default";level_suggestion?:Level|null;event_status?:"accepted"|"duplicate"|"stale";profile_status?:string; next_request?: string; interrupt?: {kind: string; prompt: string}};
export type StreamEvent = {event: "status" | "text" | "error" | "turn_end" | "block"; data: Record<string, unknown>};
export function threadId(): string {
  const alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
  const bytes = crypto.getRandomValues(new Uint8Array(26));
  return "thr_" + Array.from(bytes, (byte, i) => alphabet[byte & (i === 0 ? 7 : 31)]).join("");
}
export function newChat(): Chat {
  return {id: crypto.randomUUID(), threadId: threadId(), title: "گفت‌وگوی تازه", updatedAt: Date.now(), messages: [], level: "beginner", delivery: "step", mode: "learn"};
}
