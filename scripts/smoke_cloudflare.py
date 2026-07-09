"""對真實 Cloudflare AI Search 問一題。用法：uv run python scripts/smoke_cloudflare.py "尖山國中的提案進度？" """

import asyncio
import sys

from yarag import cloudflare


async def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "尖山國中的提案進度？"
    print("=== 檢索出處 ===")
    for c in await cloudflare.search(query):
        print(f"- {c['doc_name']} (相似度 {c['similarity']:.2f}): {c['snippet'][:80]}")
    print("=== 串流答案 ===")
    async for delta in cloudflare.stream_chat([{"role": "user", "content": query}]):
        print(delta, end="", flush=True)
    print()


asyncio.run(main())
