import type { PendingTurn, StreamEvent } from "./contracts";
export class StreamError extends Error { constructor(public code: string) { super(code); } }
export async function streamTurn(job: PendingTurn, signal: AbortSignal, onEvent: (event: StreamEvent) => void): Promise<void> {
  const response = await fetch("/api/chat/stream", {method: "POST", headers: {"Content-Type": "application/json", "X-Request-ID": job.requestId}, body: JSON.stringify(job.request), signal});
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new StreamError(payload.error?.code || "network_error");
  }
  if (!response.body || !response.headers.get("content-type")?.includes("text/event-stream")) throw new StreamError("stream_interrupted");
  const reader = response.body.getReader(); const decoder = new TextDecoder();
  let buffer = "", ended = false;
  try {
    while (true) {
      let timer: ReturnType<typeof setTimeout> | undefined;
      const {value, done} = await Promise.race([
        reader.read(),
        new Promise<never>((_, reject) => { timer = setTimeout(() => reject(new StreamError("stream_interrupted")), 65000); }),
      ]).finally(() => clearTimeout(timer));
      buffer += decoder.decode(value, {stream: !done}).replace(/\r\n/g, "\n");
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary+2);
        const event = frame.split("\n").find(line => line.startsWith("event:"))?.slice(6).trim();
        const data = frame.split("\n").filter(line => line.startsWith("data:")).map(line => line.slice(5).trimStart()).join("\n");
        if (!event || !data || !["status", "text", "block", "error", "turn_end"].includes(event)) continue;
        const parsed = JSON.parse(data);
        if (typeof parsed !== "object" || parsed === null) throw new StreamError("stream_interrupted");
        onEvent({event: event as StreamEvent["event"], data: parsed});
        if (event === "turn_end") ended = true;
      }
      if (done) break;
    }
    if (!ended) throw new StreamError("stream_interrupted");
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}
