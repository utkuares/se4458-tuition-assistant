"""The agent loop: the LLM picks tools, we run them and send the results back."""
import json
from datetime import datetime, timezone

from tools import TOOL_SCHEMAS

INSTRUCTIONS = """You are the tuition assistant of a university. You talk to one logged-in student.

Tools:
- search_tuition_policies: rules, deadlines, installments, late fees, scholarships, refunds.
  When you use it, mention the section numbers, for example "(Section 3.1)".
- get_my_tuition: the student's live tuition and balance. Never guess amounts.
- pay_tuition: prepares a payment. It does not pay. The app asks the student to confirm.

Rules:
- If a question needs both policy and balance information, call both tools.
- You can only see the logged-in student's data. If the user asks about another student,
  refuse politely. The tools do not take a student number.
- Call pay_tuition only when the user clearly asks to pay a specific amount for a term.
  "Can I pay $500?" is a question, not a payment request. Ask if the term or amount is missing.
- Never say a payment succeeded unless you received a successful payment result.
- About installments: you may say whether the student seems eligible under the policy,
  but never promise approval (Section 3.4).
- Answer in the same language as the user. Keep answers short."""


class TuitionAgent:
    def __init__(self, llm, model, tools, trace_path=None, max_steps=6):
        self.llm = llm
        self.model = model
        self.tools = tools
        self.trace_path = trace_path
        self.max_steps = max_steps
        self.previous_response_id = None
        self.notes = []

    def ask(self, question):
        """Answers one user message. May call several tools before the final answer."""
        items = [{"role": "developer", "content": n} for n in self.notes]
        items.append({"role": "user", "content": question})
        self.notes = []
        self._trace({"question": question})

        response = self._call(items)
        for _ in range(self.max_steps):
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                self._trace({"answer": response.output_text})
                return response.output_text

            outputs = []
            for call in calls:
                args = json.loads(call.arguments or "{}")
                result = self.tools.run(call.name, args)
                self._trace({"tool": call.name, "args": args, "result": result})
                outputs.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result),
                })
            response = self._call(outputs)
        return "Sorry, I could not finish this request. Please try again."

    def add_note(self, text):
        """Tells the LLM about something the app did, e.g. a confirmed payment."""
        self.notes.append(text)

    def _call(self, input_items):
        response = self.llm.responses.create(
            model=self.model,
            instructions=INSTRUCTIONS,
            tools=TOOL_SCHEMAS,
            input=input_items,
            previous_response_id=self.previous_response_id,
        )
        self.previous_response_id = response.id
        return response

    def _trace(self, data):
        if self.trace_path is None:
            return
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), **data}
        with self.trace_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")