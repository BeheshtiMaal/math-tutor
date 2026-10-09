"""Deterministic offline service clients; never a replacement graph engine."""
from collections import deque
from agent import EvidenceResult


class FakeModelClient:
    def __init__(self, responses=()):
        self.responses = deque(responses)
        self.calls = []

    async def structured(self, messages, schema):
        self.calls.append(("structured", list(messages), schema))
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return schema.model_validate(response)

    async def text(self, messages):
        self.calls.append(("text", list(messages)))
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        if not isinstance(response, str):
            raise ValueError("Fake response is not text")
        return response


class FakeSearchClient:
    def __init__(self, result=None):
        self.result = result or EvidenceResult(status="skipped", warning="Search backend disabled", retrieval_method="fake")
        self.calls = []

    async def search(self, request):
        self.calls.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result.model_copy(deep=True)


class FakeRetrievalClient:
    def __init__(self, source=None, examples=None, tips=None):
        self.results = {
            "read_source": source or EvidenceResult(status="empty", retrieval_method="fake"),
            "verified_examples": examples or EvidenceResult(status="empty", retrieval_method="fake"),
            "teaching_bestpractices": tips or EvidenceResult(status="empty", retrieval_method="fake"),
        }
        self.calls = []

    async def _get(self, name, request):
        self.calls.append((name, request))
        result = self.results[name]
        if isinstance(result, Exception):
            raise result
        return result.model_copy(deep=True)

    async def read_source(self, request):
        return await self._get("read_source", request)

    async def verified_examples(self, request):
        return await self._get("verified_examples", request)

    async def teaching_bestpractices(self, request):
        return await self._get("teaching_bestpractices", request)
