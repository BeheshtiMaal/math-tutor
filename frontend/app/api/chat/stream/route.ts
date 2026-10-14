// This server-side URL is never exposed to the browser. No provider key is used.
import {readProxyRequest} from "@/lib/server-request";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export async function POST(request: Request) {
  const input=await readProxyRequest(request);if('response' in input)return input.response;
  const bytes=input.body;
  try {
    const backend = process.env.TUTOR_BACKEND_URL || "http://127.0.0.1:8765";
    const requestId = request.headers.get("x-request-id");
    const response = await fetch(`${backend}/api/chat/stream`, {method: "POST", body: bytes,
      headers: {"Content-Type": "application/json", ...(requestId ? {"X-Request-ID": requestId} : {})}, signal: request.signal, cache: "no-store"});
    return new Response(response.body, {status: response.status, headers: {"Content-Type": response.headers.get("content-type") || "application/json", "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}});
  } catch {
    return Response.json({error: {code: "network_error", message_key: "error.network"}}, {status: 502});
  }
}
