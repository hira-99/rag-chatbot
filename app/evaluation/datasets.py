"""Test-case schemas and a small hand-written dataset for evaluating the
real app (Step 12/26's pattern) -- pointed at real retrieval/agent code,
not a notebook demo corpus.
"""
from pydantic import BaseModel


class RetrievalTestCase(BaseModel):
    case_id: str
    query: str
    expected_chunk_ids: list[str]
    category: str = "factual"


RETRIEVAL_TEST_CASES = [
    RetrievalTestCase(
        case_id="r1", query="How many days of PTO do ByteMage employees get?",
        expected_chunk_ids=["bytemage-leave-policy-0"], category="factual",
    ),
    RetrievalTestCase(
        case_id="r2", query="What is the ByteMage compensation review schedule?",
        expected_chunk_ids=["bytemage-compensation-policy-0"], category="factual",
    ),
    RetrievalTestCase(
        case_id="r3", query="What does ByteMage's onboarding process look like?",
        expected_chunk_ids=["bytemage-onboarding-guide-0"], category="factual",
    ),
]


class AgentTestCase(BaseModel):
    case_id: str
    message: str
    expected_route: str  # "plain" | "agentic" | "fixed_workflow"
    expected_tool_names: list[str] = []
    forbidden_tool_names: list[str] = []


AGENT_TEST_CASES = [
    # Confirmed live: even a large multiplication ("4187 * 2953") is flaky
    # -- gpt-4.1-mini sometimes answers from mental math instead of calling
    # the tool (~50% of runs), which makes the release gate non-deterministic.
    # A multi-step decimal expression is reliably "not mental math" territory.
    AgentTestCase(
        case_id="a1", message="What is (4187.63 * 2953.14) / 17.2, rounded to 2 decimal places?",
        expected_route="agentic", expected_tool_names=["calculate"],
    ),
    AgentTestCase(case_id="a2", message="Look up CUST-1001", expected_route="fixed_workflow"),
    AgentTestCase(
        case_id="a3", message="Hello, how are you?", expected_route="plain",
        forbidden_tool_names=["calculate", "lookup_customer"],
    ),
]
