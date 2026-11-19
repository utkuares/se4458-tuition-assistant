import asyncio

from mcp import Client

from policy_index import PolicyIndex, split_into_chunks, tokenize
from server import mcp

index = PolicyIndex()


def sections(result):
    return [m.section for m in result.matches]


def test_document_is_split_into_sections():
    ids = [c.section for c in index.chunks]

    assert len(ids) == 25
    assert ids[:4] == ["1", "2.1", "2.2", "2.3"]
    assert "9" in ids


def test_chunk_keeps_heading_and_text():
    chunks = split_into_chunks("## 3. Installments\n### 3.1 Eligibility\nAt least $300.\n")

    assert len(chunks) == 1
    assert chunks[0].section == "3.1"
    assert chunks[0].heading == "Eligibility"
    assert chunks[0].text == "At least $300."


def test_tokenize_drops_stop_words_and_plural():
    assert tokenize("What are the installments?") == ["installment"]


def test_search_payment_deadline():
    result = index.search("When is the Fall payment deadline?")

    assert "2.1" in sections(result)
    assert "September 30, 2026" in " ".join(m.text for m in result.matches)


def test_search_installment_eligibility():
    result = index.search("installment eligibility minimum balance")

    assert sections(result)[0] == "3.1"
    assert "$300" in result.matches[0].text


def test_search_refund_after_withdrawal():
    result = index.search("refund after withdrawal")

    assert set(sections(result)) & {"6.1", "6.2", "6.3"}


def test_unrelated_or_empty_query_returns_no_matches():
    assert index.search("pizza delivery").matches == []
    assert index.search("").matches == []


def test_top_k_limits_results():
    assert len(index.search("payment", top_k=2).matches) == 2


def test_mcp_tool_works_through_the_protocol():
    async def call():
        async with Client(mcp) as client:
            tools = await client.list_tools()
            result = await client.call_tool("search_tuition_policies", {"query": "late fee", "top_k": 1})
            return tools, result

    tools, result = asyncio.run(call())

    assert [t.name for t in tools.tools] == ["search_tuition_policies"]
    assert result.structured_content["document"] == "University_Tuition_Policies.md"
    assert result.structured_content["matches"][0]["section"] == "4.1"