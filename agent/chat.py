"""Command-line chat with the tuition assistant."""
import getpass
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from assistant import TuitionAgent
from tools import ToolError, TuitionTools

ROOT = Path(__file__).resolve().parents[1]


def confirm_payment(tools, agent):
    """Shows the pending payment and pays only if the user types yes."""
    p = tools.pending
    print("\n--- Payment confirmation ---")
    print(f"Student:         {p.student_no}")
    print(f"Term:            {p.term}")
    print(f"Amount:          {p.amount} {p.currency}")
    print(f"Current balance: {p.current_balance} {p.currency}")
    answer = input("Type 'yes' to confirm, anything else to cancel: ").strip().lower()

    if answer != "yes":
        tools.cancel_pending_payment()
        print("Payment cancelled.")
        agent.add_note("The user cancelled the pending payment. Nothing was paid.")
        return

    result = tools.confirm_pending_payment()
    if "error" in result:
        print(f"Payment failed: {result['error']}")
    else:
        print(f"Payment successful. Transaction: {result['transaction_id']}, "
              f"remaining balance: {result['remaining_balance']} {result['currency']}")
    agent.add_note(f"Payment result from the API: {json.dumps(result)}")


def main():
    load_dotenv(ROOT / ".env")
    tools = TuitionTools(
        gateway_url=os.getenv("GATEWAY_URL", "http://127.0.0.1:8000"),
        mcp_url=os.getenv("MCP_URL", "http://127.0.0.1:8001/mcp"),
    )

    print("Tuition Assistant - please log in")
    try:
        tools.login(input("Username: ").strip(), getpass.getpass("Password: "))
    except ToolError as e:
        print(f"Login failed: {e}")
        return
    print(f"Logged in as student {tools.student_no}. Type 'exit' to quit.")

    agent = TuitionAgent(OpenAI(), os.environ["OPENAI_MODEL"], tools,
                         trace_path=ROOT / "logs" / "trace.jsonl")
    while True:
        question = input("\nYou: ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue
        print(f"\nAssistant: {agent.ask(question)}")
        if tools.pending:
            confirm_payment(tools, agent)


if __name__ == "__main__":
    main()