"""Tools the agent can run: MCP policy search and tuition API calls through the gateway."""
import asyncio
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import httpx
from mcp import Client

PAYMENT_TTL_SECONDS = 120

TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "search_tuition_policies",
        "description": "Search the university tuition policy document (deadlines, installments, "
                       "late fees, scholarships, refunds, payment rules). Returns excerpts with "
                       "section numbers. Contains no student-specific data.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search text in English."}},
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_my_tuition",
        "description": "Get the logged-in student's live tuition, paid amount and balance. "
                       "Only works for the logged-in student.",
        "parameters": {
            "type": "object",
            "properties": {
                "term": {
                    "type": ["string", "null"],
                    "description": "Term like 2026-FALL or 2027-SPRING. null means all terms.",
                }
            },
            "required": ["term"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "pay_tuition",
        "description": "Prepare a tuition payment for the logged-in student. This does NOT pay. "
                       "The application then shows the details and asks the user to confirm.",
        "parameters": {
            "type": "object",
            "properties": {
                "term": {"type": "string", "description": "Term like 2026-FALL."},
                "amount": {"type": "number", "description": "Amount in the tuition currency."},
            },
            "required": ["term", "amount"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


class ToolError(Exception):
    pass


@dataclass
class PendingPayment:
    student_no: str
    term: str
    amount: str
    currency: str
    current_balance: str
    transaction_id: str
    expires_at: float


class TuitionTools:
    """Holds the student's session and runs the tools the LLM asks for."""

    def __init__(self, gateway_url, mcp_url, http=None, policy_search=None, clock=time.monotonic):
        self.http = http or httpx.Client(base_url=gateway_url, timeout=15)
        self.mcp_url = mcp_url
        self.policy_search = policy_search or self._search_via_mcp
        self.clock = clock
        self.token = None
        self.student_no = None
        self.pending = None

    def login(self, username, password):
        """Logs in through the gateway and remembers the token and student number."""
        r = self.http.post("/api/v1/auth/login", json={"username": username, "password": password})
        if r.status_code != 200:
            raise ToolError(self._error_message(r))
        body = r.json()
        if body["role"] != "student":
            raise ToolError("This assistant is only for students.")
        self.token = body["access_token"]
        me = self.http.get("/api/v1/auth/me", headers=self._auth())
        self.student_no = me.json()["student_no"]

    def run(self, name, args):
        """Runs one tool by name. Errors are returned to the LLM instead of crashing."""
        handlers = {
            "search_tuition_policies": self.search_tuition_policies,
            "get_my_tuition": self.get_my_tuition,
            "pay_tuition": self.pay_tuition,
        }
        if name not in handlers:
            return {"error": f"Unknown tool: {name}"}
        try:
            return handlers[name](**args)
        except ToolError as e:
            return {"error": str(e)}
        except (httpx.HTTPError, OSError) as e:
            return {"error": f"Service unavailable: {e.__class__.__name__}"}

    def search_tuition_policies(self, query):
        return self.policy_search(query)

    def _search_via_mcp(self, query):
        async def call():
            async with Client(self.mcp_url) as client:
                result = await client.call_tool("search_tuition_policies", {"query": query, "top_k": 3})
                return result.structured_content

        return asyncio.run(call())

    def get_my_tuition(self, term=None):
        params = {"term": term} if term else None
        r = self.http.get(f"/api/v1/banking/tuition/{self.student_no}", params=params, headers=self._auth())
        if r.status_code != 200:
            raise ToolError(self._error_message(r))
        return r.json()

    def pay_tuition(self, term, amount):
        """Creates a pending payment. Nothing is paid until confirm_pending_payment is called."""
        try:
            value = Decimal(str(amount)).quantize(Decimal("0.01"))
        except InvalidOperation:
            raise ToolError("Amount must be a number.")
        if value <= 0:
            raise ToolError("Amount must be positive.")

        term_info = self.get_my_tuition(term)["terms"][0]
        balance = Decimal(term_info["balance"])
        if value > balance:
            raise ToolError(f"Amount {value} exceeds the current balance {balance}.")

        self.pending = PendingPayment(
            student_no=self.student_no,
            term=term,
            amount=str(value),
            currency=term_info["currency"],
            current_balance=str(balance),
            transaction_id=f"AGENT-{uuid.uuid4()}",
            expires_at=self.clock() + PAYMENT_TTL_SECONDS,
        )
        return {
            "status": "PENDING_CONFIRMATION",
            "student_no": self.student_no,
            "term": term,
            "amount": str(value),
            "currency": term_info["currency"],
            "current_balance": str(balance),
            "note": "Payment is NOT done. The application will ask the user to confirm.",
        }

    def confirm_pending_payment(self):
        """Sends the locked pending payment to the API. Called only after the user types yes."""
        pending, self.pending = self.pending, None
        if pending is None:
            return {"error": "No pending payment."}
        if self.clock() > pending.expires_at:
            return {"error": "Confirmation expired. Please ask for the payment again."}
        r = self.http.post("/api/v1/banking/payments", headers=self._auth(), json={
            "student_no": pending.student_no,
            "term": pending.term,
            "amount": pending.amount,
            "transaction_id": pending.transaction_id,
        })
        if r.status_code != 201:
            return {"error": self._error_message(r)}
        return r.json()

    def cancel_pending_payment(self):
        self.pending = None

    def _auth(self):
        return {"Authorization": f"Bearer {self.token}"}

    @staticmethod
    def _error_message(response):
        try:
            return response.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            return f"Request failed with HTTP {response.status_code}."