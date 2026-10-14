import {readProxyRequest} from "@/lib/server-request";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export async function POST(request: Request) {
  const input=await readProxyRequest(request);if('response' in input)return input.response;
  const bytes=input.body;
  try {
    const backend = process.env.TUTOR_BACKEND_URL || "http://127.0.0.1:8765";
    const response = await fetch(`${backend}/api/ui/sample`,{method:"POST",body:bytes,
      headers:{"Content-Type":"application/json"},cache:"no-store",signal:AbortSignal.any([request.signal,AbortSignal.timeout(65000)])});
    return new Response(response.body,{status:response.status,headers:{"Content-Type":"application/json","Cache-Control":"no-store"}});
  } catch {
    return Response.json({error:{code:"network_error"}},{status:502});
  }
}
