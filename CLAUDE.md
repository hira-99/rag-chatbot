# CLAUDE.md

## What this is

A from-scratch RAG-and-agent chatbot, built by working through a structured
learning roadmap (`docs/Roadmap.pdf`) phase by phase.

- **`notebooks/step*.ipynb`** — the learning phase. Each notebook implements
  one roadmap step in isolation (retrieval, chunking, memory, tools, MCP,
  tracing, evaluation, ...) against a small fictional "ByteMage" company
  corpus. These are reference material, not production code — algorithms
  proven here get rewritten fresh for `app/`, not copy-pasted.
- **`app/`** — the Phase 8 capstone: a real, persistent, single-process
  application that integrates everything the notebooks explored. This is
  the actual product.
- **`mcp_server/`** — a standalone MCP server (calculator, knowledge search,
  customer lookup tools; a leave-policy resource; a prompt template),
  launched as a subprocess by `app/mcp/client.py`. Never imported directly.

## Architecture

`app/` is organized by concern, one subpackage per area:

| Package | Owns |
|---|---|
| `ui/` | Gradio components and event wiring — no business logic |
| `llm/` | Model client, message/context assembly, token budgeting, pricing |
| `database/` | SQLite schema (`models.py`), migrations, connections |
| `retrieval/` | Embeddings, vector/lexical search, fusion, reranking, citations |
| `ingestion/` | File loaders, cleaning, chunking, the upload pipeline |
| `tools/` | Tool registry, schemas, executor, permissions, approvals |
| `agent/` | The multi-step agent loop, planning, limits, cancellation |
| `mcp/` | MCP client, connection handling, tool namespacing |
| `memory/` | Short-term (summarization) and long-term (extraction/storage) memory |
| `observability/` | Structured tracing, metrics, redaction, cost tracking |
| `evaluation/` | Test datasets, retrieval/agent/safety metrics, regression gate |
| `workers/` | Background jobs (thread-pool based) |

Each module's docstring says what it's for in one line. `app/main.py` is the
entry point that wires everything into the Gradio UI.

## Tech stack

- **UI**: Gradio 6 (`gr.Blocks`), not `ChatInterface` — needed manual wiring
  for conversation switching, but this also exposes native events
  (`retry`, `undo`, `cancels=`) that a hand-built UI would have to
  reimplement.
- **Relational data**: SQLite at `data/app.db` (conversations, messages,
  attachments, memories, ...). No ORM — plain `sqlite3`.
- **Lexical search**: Elasticsearch (`docker-compose.yml`, port 9200).
- **Vector search**: Chroma (port 8000) — **not yet in `docker-compose.yml`**,
  currently a standalone container started separately. Known gap.
- **Model**: OpenAI API (`gpt-4.1-mini` / `text-embedding-3-small`, see
  `app/config.py`).
- **MCP**: the `mcp` SDK, pinned `<2` — `mcp` 2.x renamed `FastMCP` to
  `MCPServer`; this project targets the 1.x `FastMCP` API.

## Conventions

These came out of building Section A and hold for everything after it:

- **Prefer native platform features over hand-rolled equivalents.** Check
  the actual component/SDK API before building something yourself — Gradio's
  `retry`/`undo`/`cancels=` replaced what would have been custom buttons and
  manual state tracking.
- **Live-test before calling anything done.** Reasoning about code on paper
  has repeatedly missed real bugs that a 30-second browser click-through or
  direct SQLite query caught immediately (framework quirks, stale processes,
  event-firing edge cases). Don't trust it until you've clicked it.
- **Soft delete via `is_active`** for anything regeneratable or supersedable
  (a regenerated response, a corrected memory, a reindexed document chunk).
  Hard delete only for explicit user-initiated deletion.
- **Lazy resource creation** — don't write a database row until the first
  real write needs it. Avoids orphan rows from framework quirks (e.g.
  Gradio's `gr.State(callable)` invoking its argument both eagerly and
  per-session).
- **SQLite migrations**: `CREATE TABLE IF NOT EXISTS` for new tables;
  `PRAGMA table_info(...)` + conditional `ALTER TABLE` for new columns on
  existing tables (SQLite has no `ADD COLUMN IF NOT EXISTS`).
- **Single real user for now** (`DEFAULT_USER_ID` in `app/config.py`), but
  permission/scoping code is written as if multiple users exist — the
  architecture is real even though there's one account.

## Security notes

- **Secrets**: the only credential in this codebase is `OPENAI_API_KEY`,
  loaded once via `.env` (`python-dotenv`) in `app/config.py` and the
  root `config.py` (used only by `mcp_server/server.py`, which can't import
  `app/`). Every other module gets it by importing one of those two, never
  by reading the environment itself. Audited (grep across `app/` and
  `mcp_server/` for hardcoded key patterns, `password=`, `secret=`): clean.
  `.gitignore` already excludes `.env` and `*.db`.
- **Cost/rate limits**: `app/observability/cost.py` enforces a soft daily
  cap (message count + estimated spend) per user, checked at the start of
  every turn (`app/ui/chat.py::bot_respond`) -- a turn over the limit is
  blocked before any model call, not just logged afterward.
- **Audit trail**: every tool execution (`tool_calls`) and every approval
  decision (`pending_approvals`) is already persisted as it happens, with
  full arguments/results/timestamps. `app/database/models.py::get_audit_trail`
  is the query side; `app/ui/traces.py` (Section H) is the viewer, in its
  own "Developer" tab, separate from the chat pane.
- **Tracing and redaction** (Section H): every turn gets a trace_id; the
  retrieval call, the model call, and each tool call get their own span
  (`app/observability/tracing.py`), redacted (`redaction.py`) before
  storage. Verified live that a prompt-injection attempt embedded in an
  uploaded document (a fake "SYSTEM OVERRIDE" instructing an unapproved
  `lookup_customer` call) was fully ignored -- confirmed via the trace and
  the tool_calls table, not just by reading the reply.

## Final acceptance pass (against the roadmap's Phase 8 close-out)

Walked the roadmap's 10 "Final Capstone Tasks" and spot-checked its 15
"Final Questions" against the real running app.

**In scope and verified working**: citation-backed answers over uploaded
documents (task 1), long-term memory recall across conversations (task 2),
multi-tool agentic turns like customer-lookup-then-calculate (task 3),
tool-progress display with mid-run cancellation (task 8), and the
prompt-injection defense above (Question 11). Also verified live:
conversations/files/memories are each independently user-deletable
(Question 13), and state-changing tool calls are idempotent within a run
(Question 10, Section E).

**Explicitly out of scope** -- not built, because they were never part of
the approved B-H plan, not because they were missed: an email-sending tool
(task 4 wants "draft an email... ask before sending"), a calendar MCP
server (task 5 -- only `mcp_server/server.py`'s calculator/search/customer
tools exist), and per-region data partitioning (task 10's "do not access
records outside my assigned region" -- `memories`' personal/org scope
exists, but nothing regional). Adding any of these is a real scope
decision for a future session, not a gap to silently patch.

**Partially covered**: multi-round iterative retrieval with an explicit
"evidence is insufficient" signal (task 7) -- the agent *can* call
`search_knowledge_base` more than once via the tool-calling loop, but
there's no dedicated sufficiency check or forced second round the way
Step 21's notebook built. Comparing the active vs. an archived document
version (task 9) doesn't work today: retrieval always filters
`is_active=1` (by design, so a reindex doesn't surface stale chunks), which
also means the assistant has no way to see the *old* version to diff
against the new one.

## Running it

```bash
docker ps   # expect both "elasticsearch" and "chroma" containers Up
python -m app.main
```

Run as a module (`-m app.main`), not a script (`app/main.py`) — the
package's absolute imports need the project root on `sys.path`, which `-m`
provides and direct script execution doesn't.

## Where things live

- Roadmap: `docs/Roadmap.pdf`
- Full Phase 8 build sequence and rationale: see the plan this was built
  from (referenced in project history) — this file is the durable summary,
  that plan was the one-time execution roadmap.
