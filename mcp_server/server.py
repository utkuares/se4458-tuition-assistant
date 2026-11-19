
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402

from policy_index import PolicyIndex, PolicySearchResult  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("mcp_server")

index = PolicyIndex()
log.info("Indexed %d policy sections from %s", len(index.chunks), index.document_name)

mcp = MCPServer(
    name="tuition-policies",
    instructions="Search the university tuition policy document (deadlines, installments, "
    "late fees, scholarships, refunds, banking). It has no student-specific data.",
)


@mcp.tool(structured_output=True)
def search_tuition_policies(query: str, top_k: int = 3) -> PolicySearchResult:
    """Search the university tuition policy document.

    Use it for general rules such as payment deadlines, installment eligibility, late fees,
    scholarships, refunds and payment instructions. It does NOT contain any student's balance.
    Returns the best matching sections with section number, heading and text.
    """
    top_k = max(1, min(top_k, 5))
    result = index.search(query, top_k)
    log.info("search_tuition_policies(%r) -> %s", query, [m.section for m in result.matches])
    return result


app = mcp.streamable_http_app(stateless_http=True, json_response=True)


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("MCP_HOST", "127.0.0.1"), port=int(os.getenv("MCP_PORT", "8001")))