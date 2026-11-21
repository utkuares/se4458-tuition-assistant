import json
from types import SimpleNamespace

import httpx

from assistant import TuitionAgent
from tools import TuitionTools

SUMMARY = {
    "student_no": "20230001", "scope": "TERM", "total_tuition": "3000.00",
    "total_paid": "0.00", "balance": "3000.00",
    "terms": [{"term": "2026-FALL", "currency": "USD", "tuition": "3000.00",
               "paid": "0.00", "balance": "3000.00"}],
}


def fake_api(requests):
    """A fake gateway. Records every request so tests can check what was sent."""
    def handler(request):
        requests.append(request)
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"access_token": "t0k", "token_type": "bearer",
                                             "expires_in": 1800, "role": "student"})
        if request.url.path == "/api/v1/auth/me":
            return httpx.Response(200, json={"username": "student1", "role": "student",
                                             "student_no": "20230001"})
        if request.url.path == "/api/v1/banking/tuition/20230001":
            return httpx.Response(200, json=SUMMARY)
        if request.url.path == "/api/v1/banking/payments":
            body = json.loads(request.content)
            return httpx.Response(201, json={**body, "status": "COMPLETED", "currency": "USD",
                                             "paid_amount": body["amount"],
                                             "remaining_balance": "2500.00"})
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND", "message": "Not found."}})
    return handler


def make_tools(requests=None, clock=lambda: 0.0):
    requests = [] if requests is None else requests
    http = httpx.Client(base_url="http://gateway", transport=httpx.MockTransport(fake_api(requests)))
    tools = TuitionTools("http://gateway", "http://mcp", http=http, clock=clock,
                         policy_search=lambda q: {"query": q, "matches": [{"section": "3.1"}]})
    tools.login("student1", "Passw0rd!")
    return tools


def function_call(name, args, call_id="c1"):
    return SimpleNamespace(type="function_call", name=name, arguments=json.dumps(args), call_id=call_id)


class FakeLLM:
    """Plays back prepared responses instead of calling OpenAI."""
    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.calls = []
        self.responses = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        output, text = self.scripted.pop(0)
        return SimpleNamespace(id=f"resp_{len(self.calls)}", output=output, output_text=text)


def test_login_stores_token_and_student_number():
    tools = make_tools()

    assert tools.token == "t0k"
    assert tools.student_no == "20230001"


def test_agent_runs_both_tools_and_sends_results_back():
    tools = make_tools()
    llm = FakeLLM([
        ([function_call("get_my_tuition", {"term": None}, "c1"),
          function_call("search_tuition_policies", {"query": "installment"}, "c2")], ""),
        ([], "You owe 3000 USD and may request installments (Section 3.1)."),
    ])
    agent = TuitionAgent(llm, "test-model", tools)

    answer = agent.ask("Can I pay my balance in installments?")

    assert "Section 3.1" in answer
    sent = llm.calls[1]["input"]
    assert [o["call_id"] for o in sent] == ["c1", "c2"]
    assert json.loads(sent[0]["output"])["balance"] == "3000.00"
    assert llm.calls[1]["previous_response_id"] == "resp_1"


def test_student_number_comes_from_login_not_from_llm():
    requests = []
    tools = make_tools(requests)

    tools.run("get_my_tuition", {"term": "2026-FALL"})

    assert requests[-1].url.path == "/api/v1/banking/tuition/20230001"
    assert requests[-1].headers["Authorization"] == "Bearer t0k"


def test_pay_tuition_only_prepares_payment():
    requests = []
    tools = make_tools(requests)

    result = tools.run("pay_tuition", {"term": "2026-FALL", "amount": 500})

    assert result["status"] == "PENDING_CONFIRMATION"
    assert result["current_balance"] == "3000.00"
    assert tools.pending.amount == "500.00"
    assert not any(r.url.path.endswith("/payments") for r in requests)


def test_confirmed_payment_uses_locked_values():
    requests = []
    tools = make_tools(requests)
    tools.run("pay_tuition", {"term": "2026-FALL", "amount": 500})
    tx = tools.pending.transaction_id

    result = tools.confirm_pending_payment()

    body = json.loads(requests[-1].content)
    assert body == {"student_no": "20230001", "term": "2026-FALL", "amount": "500.00", "transaction_id": tx}
    assert result["status"] == "COMPLETED"
    assert tools.pending is None


def test_expired_confirmation_is_rejected():
    now = [0.0]
    requests = []
    tools = make_tools(requests, clock=lambda: now[0])
    tools.run("pay_tuition", {"term": "2026-FALL", "amount": 500})
    now[0] = 121

    result = tools.confirm_pending_payment()

    assert "expired" in result["error"]
    assert not any(r.url.path.endswith("/payments") for r in requests)


def test_amount_above_balance_is_rejected():
    tools = make_tools()

    result = tools.run("pay_tuition", {"term": "2026-FALL", "amount": 5000})

    assert "exceeds" in result["error"]
    assert tools.pending is None


def test_unknown_tool_returns_error():
    tools = make_tools()

    assert "Unknown tool" in tools.run("delete_database", {})["error"]


def test_payment_note_is_sent_with_next_question():
    tools = make_tools()
    llm = FakeLLM([([], "Done.")])
    agent = TuitionAgent(llm, "test-model", tools)
    agent.add_note("Payment result from the API: {...}")

    agent.ask("Thanks")

    roles = [item["role"] for item in llm.calls[0]["input"]]
    assert roles == ["developer", "user"]

def test_trace_has_question_tool_call_and_answer(tmp_path):
    tools = make_tools()
    llm = FakeLLM([
        ([function_call("get_my_tuition", {"term": None})], ""),
        ([], "You owe 3000 USD."),
    ])
    trace = tmp_path / "trace.jsonl"
    agent = TuitionAgent(llm, "test-model", tools, trace_path=trace)

    agent.ask("What is my balance?")

    lines = [json.loads(line) for line in trace.read_text().splitlines()]
    assert lines[0]["question"] == "What is my balance?"
    assert lines[1]["tool"] == "get_my_tuition"
    assert lines[1]["result"]["balance"] == "3000.00"
    assert lines[2]["answer"] == "You owe 3000 USD."
