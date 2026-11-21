# SE 4458 Midterm 1 – AI Tuition Assistant (Group 1)

**Student:** Hakan Utku Taşkın
**Course:** SE 4458 Software Architecture & Design of Modern Large Scale Systems

A chat assistant for tuition questions. An LLM agent decides which tool to use:
the MCP server (search in `University_Tuition_Policies.md`), the Tuition REST API
(always through the Kong API Gateway), or both.

- **Gateway (Azure):** https://tuition-gateway.wonderfulbeach-f2176740.swedencentral.azurecontainerapps.io
- **Swagger:** https://tuition-gateway.wonderfulbeach-f2176740.swedencentral.azurecontainerapps.io/docs
- **MCP server (Azure):** https://tuition-mcp.wonderfulbeach-f2176740.swedencentral.azurecontainerapps.io/mcp
- **Video:** _link here_

## Architecture

```
User (CLI) ── AI Agent ── LLM (OpenAI gpt-6-luna, function calling)
                 │
                 ├── MCP client ──► MCP Server ──► BM25 search over the policy document
                 │
                 └── HTTPS + JWT ──► Kong Gateway ──► Tuition REST API (FastAPI) ──► PostgreSQL
```

The agent never talks to the API directly. Every REST call (also the agent's) goes
through Kong. Kong checks the JWT and rate limits before the request reaches the API.

## Tech stack

| Component | Choice |
|---|---|
| REST API | Python, FastAPI, Pydantic v2 |
| Database | PostgreSQL 16, SQLAlchemy 2, Alembic |
| Auth | JWT RS256 (python-jose), bcrypt password hashes |
| API Gateway | Kong Gateway 3.9 OSS (DB-less) |
| MCP | Official `mcp` Python SDK, streamable HTTP, BM25 (`rank_bm25`) |
| Agent | OpenAI SDK (Responses API), model `gpt-6-luna` |
| Tests | pytest |
| Cloud | Azure Container Apps, Azure Container Registry, Azure Database for PostgreSQL |

## Repository layout

```
api/            FastAPI service, models, Alembic migrations, tests
mcp_server/     MCP server, policy index, tests
agent/          AI agent (tools, agent loop, CLI), tests
gateway/        Kong config template, Dockerfile, smoke test
scripts/        key generation, seed data, Kong config render, Azure deploy
data/           policy document, sample batch CSV
docs/           ER diagram, screenshots, demo logs
```

## REST API

All paths start with `/api/v1`. Swagger UI is at `/docs`.

| Method | Path | Who can call | Description |
|---|---|---|---|
| GET | `/health` | public | health check |
| POST | `/auth/login` | public | returns a JWT |
| GET | `/auth/me` | any logged in user | current user info |
| GET | `/mobile/tuition/{student_no}` | public | tuition query for the mobile app, 3 per student per day |
| GET | `/banking/tuition/{student_no}` | bank, student (only own) | tuition query for banking |
| POST | `/banking/payments` | bank, student (only own) | pay tuition |
| POST | `/admin/tuition` | admin | add or update one tuition record |
| POST | `/admin/tuition/batch` | admin | add tuition from a CSV file |
| GET | `/admin/tuition/unpaid?term=...` | admin | unpaid tuition list, paged |

**Error format.** Every API error has the same shape:

```json
{"error": {"code": "FORBIDDEN_RESOURCE", "message": "Students can only view their own tuition.", "details": []}}
```

Some codes: `INVALID_CREDENTIALS`, `MISSING_TOKEN`, `INVALID_TOKEN`, `FORBIDDEN_ROLE`,
`FORBIDDEN_RESOURCE`, `STUDENT_NOT_FOUND`, `TUITION_NOT_FOUND`, `DUPLICATE_TRANSACTION`,
`DAILY_LIMIT_EXCEEDED`, `INVALID_CSV`, `VALIDATION_ERROR`.

**Payments** need a `transaction_id`. The same id is accepted only once, so a retry
does not pay twice (`409 DUPLICATE_TRANSACTION`).

## API Gateway (Kong)

Kong runs DB-less with a declarative file (`gateway/kong.template.yml`).
`scripts/render_kong_config.py` puts the upstream URL and the JWT public key into it.

| Route | Plugins |
|---|---|
| `/api/v1/health`, `/docs`, `/openapi.json` | none |
| `/api/v1/auth` | rate limit 20/min per IP |
| `/api/v1/banking` | JWT (RS256) |
| `/api/v1/admin` | JWT (RS256) |
| `/api/v1/mobile` | rate limit 10/min per IP |

- Kong checks the token signature and `exp`. The API checks the role and the student number again.
- The "3 queries per student per day" rule is in the API, because it needs the database
  (Kong only knows the IP, not the student). Kong's per-minute limit protects against floods.
- `gateway/smoke_test.sh` tests all of this. Results: `docs/logs/gateway_demo.txt` (local)
  and `docs/logs/gateway_demo_azure.txt` (Azure).

## MCP server

`mcp_server/server.py` has one tool: `search_tuition_policies(query, top_k)`.
The policy document is split into sections and indexed with BM25. The tool returns
the best sections with their section numbers, so the agent can cite them
(for example "Section 3.4").

Demo logs: `docs/logs/mcp_demo_client.txt`, `docs/logs/mcp_demo_server.txt`.

## AI Agent

The agent (`agent/`) uses OpenAI function calling with three tools:

| Tool | Goes to |
|---|---|
| `search_tuition_policies` | MCP server |
| `get_my_tuition` | Kong → `GET /banking/tuition/{student_no}` |
| `pay_tuition` | Kong → `POST /banking/payments` |

- The user logs in first. The student number comes from the login (`/auth/me`),
  not from the LLM, so the agent cannot ask for another student's data.
- Payments are two steps. `pay_tuition` only creates a pending payment (valid for 120 s).
  The CLI shows the details and the user must type `yes`. Only then the code sends the
  payment. The LLM cannot confirm a payment by itself.
- Every LLM call and tool call is written to `logs/trace.jsonl`.
  Example: `docs/logs/agent_trace.jsonl`, chat: `docs/logs/agent_demo_chat.txt`.

**LLM cost.** OpenAI API with a prepaid limit of $5. The whole development and testing
used only a small part of it.

## Data model

See [docs/er-diagram.md](docs/er-diagram.md).

## Run locally

```bash
cp .env.example .env              # then add OPENAI_API_KEY
docker compose up -d db db_test

python -m venv .venv && source .venv/bin/activate
pip install -r api/requirements.txt -r mcp_server/requirements.txt -r agent/requirements.txt

python scripts/generate_keys.py   # RS256 key pair -> keys/
cd api && alembic upgrade head && cd ..
python scripts/seed.py            # demo students, tuitions, users

python scripts/render_kong_config.py
docker compose up -d gateway      # Kong on http://localhost:8080

(cd api && uvicorn app.main:app --port 8000)          # terminal 1
python mcp_server/server.py                          # terminal 2
python agent/chat.py                                 # terminal 3
```

Demo accounts (password `Passw0rd!`): `student1` / `student2` / `student3`
(students 20230001–3), `bank1` (bank role), `admin1` (admin role).

## Tests

54 tests in total (API, MCP server, agent). The agent tests use a fake LLM and a mock
HTTP transport, so they do not cost money.

```bash
cd api && pytest && cd ..
cd mcp_server && pytest && cd ..
cd agent && pytest && cd ..
./gateway/smoke_test.sh           # needs Kong and the API running
```

## Azure deployment

| Resource | Name |
|---|---|
| Resource group | `rg-tuition` |
| Container Registry | `tuitionacr12088` |
| PostgreSQL Flexible Server | `tuition-pg-16772` (Sweden Central) |
| Container Apps environment | `tuition-env` (Sweden Central) |
| Container App | `tuition-gateway` (Kong + API) |
| Container App | `tuition-mcp` |

- The environment is an "express" Container Apps environment. It allows only one
  container per app and has no internal DNS between apps. So Kong and the API run in
  **one container** (`gateway/Dockerfile`, `gateway/start.sh`). The API listens on
  `127.0.0.1:8000` and only Kong (port 8080) is public. The API cannot be reached
  without going through Kong.
- The student subscription does not allow ACR Tasks, so images are built locally with
  `docker buildx --platform linux/amd64` and pushed.
- Secrets (DB URL, JWT keys) are Container App secrets, not in the image or the repo.
- Deploy the gateway: `./scripts/deploy_gateway_azure.sh` (reads a local `azure.env`, not committed).

## Assumptions

- Currency is USD, like the policy document. No currency conversion.
- Terms use the format `YYYY-FALL` / `YYYY-SPRING` (policy section 1).
- Money is stored as `NUMERIC(12,2)` and handled as `Decimal`. JSON amounts are strings (`"1500.00"`).
- No overpayment: a payment cannot be more than the current balance (policy 7.2).
- The mobile daily limit counts per student number per calendar day (Europe/Istanbul time).
  Queries for unknown student numbers also count.
- The mobile route has no login, like the assignment describes. It is protected by the
  daily limit and Kong's per-IP rate limit.
- Payments are simulated records. No real money or card processing.
- The agent can not approve installments. It only explains the rules (policy 3.4).
