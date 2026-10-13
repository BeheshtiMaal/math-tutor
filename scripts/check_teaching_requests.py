"""Opt-in live HTTP-contract probes for ordinary teaching intent and derivative coverage."""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx
from agent import load_config
from webapp.main import create_app, build_service
from webapp.settings import ServerSettings
from webapp.threads import new_thread_id


async def main():
    config, credentials = load_config()
    config.preferences = config.preferences.model_copy(update={'mode': 'answer', 'language': None})
    service = build_service(settings=ServerSettings(), config=config, credentials=credentials)
    app = create_app()
    app.state.service = service
    rows = []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', trust_env=False, timeout=180) as client:
        for query in ('hey explain me logarithm', 'Explain the definition of derivative', 'Explain the chain rule for derivatives'):
            thread_id = new_thread_id()
            response = await client.post('/api/chat/turn', json={'thread_id': thread_id, 'message': query})
            body = response.json()
            degraded = any('Explanation synthesis failed' in warning for warning in body.get('warnings', []))
            state = service.graph.get_state({'configurable': {'thread_id': thread_id}}).values
            rows.append(dict(query=query, http_status=response.status_code, degraded=degraded,
                             selected_example_id=state.get('selected_example_id'),
                             evidence_request=state.get('evidence_request'), response=body))
            print(json.dumps(dict(query=query, http_status=response.status_code,
                                 mode=body.get('mode'), topic=body.get('topic'),
                                 status=body.get('status'), degraded=degraded), ensure_ascii=True), flush=True)
    payload = dict(generated_at=datetime.now(timezone.utc).isoformat(),
                   scope='three live model/retrieval probes via ASGI HTTP handlers; no mode or topic supplied', rows=rows)
    (ROOT / 'sources/manifests/teaching_request_checks.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if all(row['http_status'] == 200 and row['response'].get('mode') == 'learn'
                    and not row['degraded'] for row in rows) else 2

if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
