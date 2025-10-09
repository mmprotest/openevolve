import asyncio

import httpx

from openevolve.diffs import is_valid_diff
from openevolve.llm_client import OpenEvolveClient


def _mock_response(request: httpx.Request) -> httpx.Response:
    data = {
        "choices": [
            {
                "message": {
                    "content": "<<<<<<< SEARCH\nfoo\n=======\nbar\n>>>>>>> REPLACE"
                }
            }
        ]
    }
    return httpx.Response(200, json=data)

def test_generate_returns_candidates():
    async def _run() -> None:
        transport = httpx.MockTransport(_mock_response)
        async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as async_client:
            client = OpenEvolveClient(client=async_client, diff_validator=is_valid_diff)
            result = await client.generate(prompt="test", system="system")
            assert result.candidates == ["<<<<<<< SEARCH\nfoo\n=======\nbar\n>>>>>>> REPLACE"]

    asyncio.run(_run())
