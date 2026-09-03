"""ByteMage MCP server -- calculate, search_knowledge_base, lookup_customer
tools, the leave policy resource, and a policy-summary prompt. Runs over
stdio; launched as a subprocess by the client, never imported directly."""
import ast
import functools
import operator
import sqlite3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import chromadb
from elasticsearch import Elasticsearch
from mcp.server.fastmcp import FastMCP
from openai import OpenAI

from config import OPENAI_API_KEY, EMBEDDING_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)
es = Elasticsearch("http://localhost:9200")
client_chroma = chromadb.HttpClient(host="localhost", port=8000)

INDEX_NAME = "rag_documents_agentic"
COLLECTION_NAME = "bytemage_agentic_docs"
collection = client_chroma.get_or_create_collection(name=COLLECTION_NAME)

mcp_server = FastMCP("bytemage-server")


def log_tool_call(func):
    """Server-side logging (roadmap item 11) -- stderr only. Printing to
    stdout would corrupt the stdio JSON-RPC stream the protocol uses."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        duration_ms = (time.perf_counter() - start) * 1000
        success = result.get("success", True) if isinstance(result, dict) else True
        print(f"[mcp-server] tool={func.__name__} success={success} duration_ms={duration_ms:.1f}", file=sys.stderr)
        return result
    return wrapper


# ---- Tool 1: calculator (same safe AST-based implementation as Step 16) ----
@mcp_server.tool()
@log_tool_call
def calculate(expression: str) -> dict:
    """Evaluate a basic arithmetic expression (+, -, *, /)."""
    ops = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.USub: operator.neg,
    }

    def eval_node(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp):
            return ops[type(node.op)](eval_node(node.left), eval_node(node.right))
        if isinstance(node, ast.UnaryOp):
            return ops[type(node.op)](eval_node(node.operand))
        raise ValueError("unsupported expression")

    try:
        tree = ast.parse(expression, mode="eval")
        return {"success": True, "result": eval_node(tree.body)}
    except Exception:
        # Validation-style error -- safe to describe, not a stack trace.
        return {"success": False, "error_type": "invalid_expression", "message": f"could not evaluate {expression!r}"}


# ---- Tool 2: knowledge search (same hybrid search as Step 21) ----
def get_embedding(text):
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


@mcp_server.tool()
@log_tool_call
def search_knowledge_base(query: str, top_k: int = 5) -> dict:
    """Search ByteMage's internal knowledge base. Returns short previews."""
    try:
        vector_raw = collection.query(query_embeddings=[get_embedding(query)], n_results=10)
        vector_results = [
            {"chunk_id": cid, "text": vector_raw["documents"][0][i]}
            for i, cid in enumerate(vector_raw["ids"][0])
        ]

        lexical_raw = es.search(index=INDEX_NAME, body={"size": 10, "query": {"match": {"text": query}}})
        lexical_results = [
            {"chunk_id": hit["_source"]["chunk_id"], "text": hit["_source"]["text"]}
            for hit in lexical_raw["hits"]["hits"]
        ]

        scores, chunks = {}, {}
        for rank, r in enumerate(vector_results, start=1):
            chunks[r["chunk_id"]] = r["text"]
            scores[r["chunk_id"]] = scores.get(r["chunk_id"], 0) + 1 / (60 + rank)
        for rank, r in enumerate(lexical_results, start=1):
            chunks[r["chunk_id"]] = r["text"]
            scores[r["chunk_id"]] = scores.get(r["chunk_id"], 0) + 1 / (60 + rank)

        ranked = sorted(scores, key=scores.get, reverse=True)[:top_k]
        return {
            "success": True,
            "query": query,
            "results": [
                {"chunk_id": cid, "preview": chunks[cid][:120], "score": round(scores[cid], 4)}
                for cid in ranked
            ],
        }
    except Exception as e:
        # Infra-level failure -- log the real cause server-side, never send
        # the raw exception (which could include hosts/ports) to the client.
        print(f"[mcp-server] search_knowledge_base failed: {e!r}", file=sys.stderr)
        return {"success": False, "error_type": "internal_failure", "message": "search is temporarily unavailable"}


# ---- Tool 3: read-only customer lookup (SQLite) ----
CUSTOMER_DB_PATH = PROJECT_ROOT / "data" / "mcp_customers.db"


def _init_customer_db():
    CUSTOMER_DB_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(CUSTOMER_DB_PATH, check_same_thread=False)
    conn.execute("CREATE TABLE customers (customer_id TEXT PRIMARY KEY, name TEXT, email TEXT, company TEXT, notes TEXT)")
    conn.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
        [
            ("CUST-001", "Dana Whitfield", "dana@northwind.example", "Northwind Traders", "Frequent escalations."),
            ("CUST-002", "Marcus Lee", "marcus@initech.example", "Initech", "VIP account."),
            ("CUST-003", "Sara Chin", "sara@globex.example", "Globex", ""),
        ],
    )
    conn.commit()
    return conn


_customer_conn = _init_customer_db()


@mcp_server.tool()
@log_tool_call
def lookup_customer(customer_id: str | None = None, email: str | None = None, company: str | None = None) -> dict:
    """Look up a customer by ID, email, or company name. Returns limited fields only -- never internal notes."""
    if not any([customer_id, email, company]):
        return {"success": False, "error_type": "invalid_query", "message": "provide customer_id, email, or company"}

    clauses, params = [], []
    if customer_id:
        clauses.append("customer_id = ?"); params.append(customer_id)
    if email:
        clauses.append("email = ?"); params.append(email)
    if company:
        clauses.append("company = ?"); params.append(company)

    rows = _customer_conn.execute(
        f"SELECT customer_id, name, email, company FROM customers WHERE {' OR '.join(clauses)}", params
    ).fetchall()

    if not rows:
        return {"success": False, "error_type": "not_found", "message": "no matching customer"}

    return {
        "success": True,
        "customers": [{"customer_id": r[0], "name": r[1], "email": r[2], "company": r[3]} for r in rows],
    }


# ---- Resource: leave policy ----
LEAVE_POLICY_TEXT = (
    "ByteMage employees may take up to five sick days per month without additional "
    "approval. Extended sick leave beyond five days requires notifying HR within 48 "
    "hours and is approved by the employee's direct manager. Unused sick days do not "
    "roll over to the next month and are forfeited at month end."
)


@mcp_server.resource("company://policies/leave")
def leave_policy_resource() -> str:
    """The current ByteMage leave policy."""
    return LEAVE_POLICY_TEXT


# ---- Prompt template ----
@mcp_server.prompt()
def summarize_policy(policy_name: str) -> str:
    """Summarize a company policy for an employee."""
    return f"Summarize the {policy_name} policy in plain, friendly language for a new ByteMage employee. Keep it under 3 sentences."


if __name__ == "__main__":
    mcp_server.run(transport="stdio")
