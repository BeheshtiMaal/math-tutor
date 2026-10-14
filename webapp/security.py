"""Bound actual (including chunked) request bytes before JSON parsing."""
from starlette.responses import JSONResponse
import json

class LocalRequestGuard:
    def __init__(self, app, *, max_bytes, origins):
        self.app, self.max_bytes, self.origins = app, max_bytes, set(origins)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in {'POST','PUT','PATCH'}:
            return await self.app(scope,receive,send)
        headers=dict(scope['headers'])
        origin=headers.get(b'origin')
        if origin is not None and origin.decode('latin-1') not in self.origins:
            return await JSONResponse({'error':{'code':'bad_request','message_key':'error.origin'}},status_code=403)(scope,receive,send)
        chunks, size = [], 0
        while True:
            message=await receive()
            if message['type']=='http.disconnect': return
            chunk=message.get('body',b'');size+=len(chunk)
            if size>self.max_bytes:
                return await JSONResponse({'error':{'code':'payload_too_large','message_key':'error.payload_too_large'}},status_code=413)(scope,receive,send)
            chunks.append(chunk)
            if not message.get('more_body',False):break
        replayed=False
        body=b''.join(chunks)
        def bounded_number(value):
            if len(value)>128:raise ValueError('Numeric token too long')
            return 0
        media_type=headers.get(b'content-type',b'').split(b';',1)[0].strip().lower()
        if body and (not media_type or media_type==b'application/json' or media_type.endswith(b'+json')):
            try:json.loads(body,parse_int=bounded_number,parse_float=bounded_number)
            except (ValueError,RecursionError,UnicodeError):
                return await JSONResponse({'error':{'code':'bad_request','message_key':'error.bad_request'}},status_code=400)(scope,receive,send)
        async def bounded_receive():
            nonlocal replayed
            if not replayed:
                replayed=True
                return {'type':'http.request','body':body,'more_body':False}
            return await receive()
        await self.app(scope,bounded_receive,send)
