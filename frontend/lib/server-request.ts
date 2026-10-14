// Bound local proxy requests before retaining their body or forwarding them.
const ORIGINS=new Set(["http://127.0.0.1:3000","http://localhost:3000"]);
export async function readProxyRequest(request:Request,maxBytes=262144):Promise<{body:ArrayBuffer}|{response:Response}>{
  const error=(code:string,status:number)=>({response:Response.json({error:{code}},{status})});
  if(!ORIGINS.has(new URL(request.url).origin))return error("bad_request",403);
  const origin=request.headers.get("origin");
  if(origin&&!ORIGINS.has(origin))return error("bad_request",403);
  const declared=request.headers.get("content-length");
  if(declared&&(!/^\d+$/.test(declared)||Number(declared)>maxBytes))return error("payload_too_large",413);
  if(!request.body)return {body:new ArrayBuffer(0)};
  const reader=request.body.getReader(),chunks:Uint8Array[]=[];let length=0;
  try{
    while(true){const {done,value}=await reader.read();if(done)break;length+=value.byteLength;
      if(length>maxBytes){await reader.cancel();return error("payload_too_large",413);}chunks.push(value);}
    const body=new Uint8Array(length);let offset=0;for(const chunk of chunks){body.set(chunk,offset);offset+=chunk.byteLength;}
    return {body:body.buffer};
  }catch{return error("bad_request",400);}finally{reader.releaseLock();}
}
