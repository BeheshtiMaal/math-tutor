import { describe, expect, it, vi } from "vitest";
import { streamTurn } from "@/lib/stream";
import { newChat, type PendingTurn } from "@/lib/contracts";
const job=():PendingTurn=>({requestId:"same-turn",messageId:"reply",request:{thread_id:newChat().threadId,message:"Explain derivatives",action:"new_lesson",mode:"learn",delivery:"step",level:"beginner",level_source:"manual"}});
describe("SSE",() => {
  it("decodes split UTF-8 and ordered deltas and requires the final event",async () => {
    const bytes=new TextEncoder().encode('event: text\ndata: {"segment_index":0,"kind":"text","delta":"سلام"}\n\nevent: turn_end\ndata: {"awaiting_user":true}\n\n');
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue(new Response(new ReadableStream({start(c){for(let i=0;i<bytes.length;i+=3)c.enqueue(bytes.slice(i,i+3));c.close();}}),{headers:{"content-type":"text/event-stream"}})));
    const events:string[]=[];await streamTurn(job(),new AbortController().signal,event=>events.push(event.event));expect(events).toEqual(["text","turn_end"]);
    vi.unstubAllGlobals();
  });
  it("reports an interrupted stream rather than silently accepting a partial reply",async () => {
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue(new Response('event: status\ndata: {"state":"writing"}\n\n',{headers:{"content-type":"text/event-stream"}})));
    await expect(streamTurn(job(),new AbortController().signal,()=>{})).rejects.toThrow("stream_interrupted");vi.unstubAllGlobals();
  });
});
