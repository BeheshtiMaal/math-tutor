import {describe,it,expect} from "vitest";
import {readProxyRequest} from "@/lib/server-request";

describe("local request boundary",()=>{
 it("rejects hostile origins before reading the body",async()=>{
  const request=new Request("http://127.0.0.1:3000/api/chat/stream",{method:"POST",body:"{}"});
  request.headers.set("origin","https://attacker.example");
  const result=await readProxyRequest(request);
  expect('response' in result&&result.response.status).toBe(403);
 });
 it("bounds actual streamed bytes when Content-Length is absent or understated",async()=>{
  for(const headers of [{},{"content-length":"1"}]){
   let cancelled=false;
   const body=new ReadableStream<Uint8Array>({start(controller){controller.enqueue(new Uint8Array(600));controller.enqueue(new Uint8Array(600));},cancel(){cancelled=true;}});
   const request=new Request("http://127.0.0.1:3000/api/chat/stream",{method:"POST",headers,body,duplex:"half"} as RequestInit);
   const result=await readProxyRequest(request,1024);
   expect('response' in result&&result.response.status).toBe(413);expect(cancelled).toBe(true);
  }
 });
 it("preserves bounded local JSON and rejects an untrusted Host URL",async()=>{
  const result=await readProxyRequest(new Request("http://localhost:3000/api/chat/stream",{method:"POST",body:'{"message":"سلام"}'}));
  expect('body' in result&&new TextDecoder().decode(result.body)).toBe('{"message":"سلام"}');
  const hostile=await readProxyRequest(new Request("http://attacker.example:3000/api/chat/stream",{method:"POST",body:"{}"}));
  expect('response' in hostile&&hostile.response.status).toBe(403);
 });
});
