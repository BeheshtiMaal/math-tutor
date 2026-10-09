"""Bounded asynchronous Tavily search. No requests or secrets at import time."""
import asyncio
from datetime import datetime, timezone
import json
from urllib.parse import urlsplit

import httpx
from agent import EvidenceResult, WebRecord
from learning import bounded


class TavilySearchClient:
    def __init__(self, config, credentials, *, transport=None):
        self.config, self.credentials, self.transport = config, credentials, transport

    async def search(self, request):
        if not self.config.search_enabled:
            return EvidenceResult(status="skipped", warning="Web search is disabled.")
        if self.credentials.search_api_key is None:
            return EvidenceResult(status="skipped", warning="Web search key is missing; local evidence remains available.")
        try:
            return await asyncio.wait_for(self._search(request), self.config.limits.request_timeout_seconds)
        except Exception:
            return EvidenceResult(status="error", warning="Web search failed or timed out; local evidence remains available.")

    async def _search(self, request):
        payload = {"query": request.query, "topic": "general", "search_depth": "basic",
                   "max_results": min(request.max_records, 5), "include_answer": False,
                   "include_raw_content": False, "include_images": False, "auto_parameters": False}
        avalai = self.config.search_backend == "avalai_tavily"
        endpoint = self.config.search_url or ("https://api.avalai.ir/v1/search/tavily-search" if avalai else "https://api.tavily.com/search")
        if avalai:
            payload = {"query": request.query, "max_results": min(request.max_records, 5), "max_tokens_per_page": 512}
        async with httpx.AsyncClient(timeout=self.config.limits.request_timeout_seconds,
                                     follow_redirects=False, transport=self.transport) as client:
            async with client.stream("POST", endpoint, json=payload,
                headers={"Authorization": "Bearer " + self.credentials.search_api_key.get_secret_value()}) as response:
                response.raise_for_status()
                data = bytearray()
                async for part in response.aiter_bytes():
                    data.extend(part)
                    if len(data) > 1_000_000:
                        raise ValueError("Search response exceeds budget")
        rows = json.loads(data)["results"]
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError("Invalid search result list")
        records, seen, excluded = [], set(), False
        retrieved = datetime.now(timezone.utc)
        for row in rows:
            try:
                record = WebRecord(title=row["title"], text=row["snippet"] if avalai else row["content"], source_url=row["url"], retrieved_at=retrieved)
                url = str(record.source_url)
                if urlsplit(url).username or urlsplit(url).password or len(record.text) > request.max_chars:
                    raise ValueError("Unsupported result")
                if url in seen:
                    continue
                seen.add(url)
                records.append(record)
            except (ValueError, KeyError, TypeError):
                excluded = True
        warning = "Search snippets are supplementary, not complete reviewed sources or verified calculations."
        if excluded:
            warning += " Invalid/oversized results were excluded."
        result = bounded(records, request, warning)
        return result.model_copy(update={"retrieval_method": "web"})
