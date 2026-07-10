"""對真 OpenAI 問一題。用法：uv run python scripts/smoke_openai.py "最近的教育新聞？" """

import asyncio
import sys

from yarag import openai_client


async def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else "台灣最近的教育政策新聞？"
    async for kind, value in openai_client.stream_web_answer(question):
        if kind == "delta":
            print(value, end="", flush=True)
        else:
            print("\n=== 來源 ===")
            for s in value:
                print(f"- {s['doc_name']}: {s['url']}")


asyncio.run(main())
