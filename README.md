# Framework-Free RAG & AI Agents

A RAG-and-agent chatbot built from first principles — direct **Python** and
**API/SDK calls**, no LangChain/LlamaIndex/CrewAI/AutoGen — taken from a
basic chatbot all the way to a real, persistent application with hybrid
retrieval, tool-calling agents, MCP integration, memory, and a working
evaluation/tracing pipeline.

Two things live here:

- **`notebooks/`** — the learning phase. 15 notebooks, each isolating one
  concept (retrieval, chunking, memory, tool calling, agent loops, MCP,
  tracing, evaluation) against a small fictional company corpus.
- **`app/`** — the capstone. A real Gradio application that integrates
  everything the notebooks explored, rewritten fresh (not copy-pasted)
  against SQLite, Elasticsearch, and Chroma. ~90 files, live-tested
  through the running app at every stage rather than trusted on paper.

## What it can do

- Answer questions grounded in your own uploaded documents, with
  numbered citations that are validated against the real sources after
  the fact — not just trusted because the model wrote them
- Search with **hybrid retrieval** (vector + BM25, fused with Reciprocal
  Rank Fusion) and an **LLM-based reranker** for a second, precision pass
- Call tools — a calculator, knowledge search, a customer lookup — through
  a real agent loop that can cancel mid-run and won't repeat an identical
  call twice in one turn
- Pause and ask a human before running a sensitive action, and resume
  exactly where it left off once approved or rejected
- Connect to external tools over **MCP** (built both a real server and a
  real client), with every MCP-sourced tool requiring approval by default
- Remember short-term context via rolling summarization and long-term
  facts via extraction + embedding-based duplicate/conflict resolution
- Trace every turn (retrieval, model calls, tool calls) into inspectable
  spans, with a real evaluation suite and a regression gate that blocks a
  release when a measured threshold fails
- Resist prompt injection — verified live: a malicious instruction
  embedded in a retrieved document was ignored, confirmed against the
  database, not just the reply

## Architecture

| Package | Owns |
|---|---|
| `ui/` | Gradio components and event wiring |
| `llm/` | Model client, context assembly, token budgeting, pricing |
| `retrieval/` | Embeddings, vector/lexical search, fusion, reranking, citations |
| `ingestion/` | File loaders, cleaning, chunking, the upload pipeline |
| `tools/` | Tool registry, executor, permissions, approvals, idempotency |
| `agent/` | The tool-calling loop, planning, limits, cancellation |
| `mcp/` | MCP client, connection handling, tool namespacing |
| `memory/` | Short-term summarization and long-term extraction/storage |
| `observability/` | Tracing, metrics, redaction, cost tracking |
| `evaluation/` | Test datasets, metrics, the regression release gate |
| `database/` | SQLite schema and migrations (no ORM) |

## Stack

Gradio 6 · SQLite · Elasticsearch (lexical) · Chroma (vector) · OpenAI
(`gpt-4.1-mini` / `text-embedding-3-small`) · the `mcp` SDK

## Running it

```bash
docker compose up -d          # Elasticsearch
docker run -d -p 8000:8000 chromadb/chroma   # Chroma (not yet in compose)
python -m app.main
```

Run as a module (`-m app.main`), not a script — the package's imports
need the project root on `sys.path`. Needs an `OPENAI_API_KEY` in `.env`.

## Why no framework

The point of building this without LangChain/LangGraph/etc. was to
actually understand what those frameworks abstract away — rank fusion,
an agent loop, a permission-checked tool executor, a redacted trace span
— before ever reaching for one. Infrastructure libraries (model SDKs,
`elasticsearch`, `chromadb`, `pydantic`, the `mcp` SDK itself) are fair
game throughout; orchestration frameworks were the thing being avoided.
