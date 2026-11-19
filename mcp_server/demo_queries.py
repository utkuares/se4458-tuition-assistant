"""Calls the running MCP server with three different questions and prints the results.

Run the server first (python mcp_server/server.py), then:  python mcp_server/demo_queries.py
"""
import asyncio
import os

from mcp import Client

MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8001/mcp")

QUERIES = [
    "When is the Fall payment deadline?",
    "installment eligibility minimum balance",
    "refund after withdrawal",
]


async def main() -> None:
    async with Client(MCP_URL) as client:
        tools = await client.list_tools()
        print("Tools on server:", [t.name for t in tools.tools])

        for query in QUERIES:
            result = await client.call_tool("search_tuition_policies", {"query": query, "top_k": 2})
            print(f"\nQuery: {query}")
            for match in result.structured_content["matches"]:
                print(f"  [{match['section']}] {match['heading']}  (score {match['score']})")
                print(f"      {match['text'][:110]}...")


if __name__ == "__main__":
    asyncio.run(main())