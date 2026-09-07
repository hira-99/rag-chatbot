"""Model pricing table and cost calculation.

Prices are $ per 1M tokens (OpenAI's published pricing for the models this
app uses, at time of writing -- check OpenAI's pricing page if this drifts).
Used for a rough per-request/per-day cost estimate (app/observability/cost.py),
not exact billing: the app stores one token_count per message, not separate
input/output counts per model call.
"""

MODEL_PRICING = {
    "gpt-4.1-mini": {"input_per_million": 0.40, "output_per_million": 1.60},
    "text-embedding-3-small": {"input_per_million": 0.02, "output_per_million": 0.0},
}


def estimate_cost(model_name, input_tokens=0, output_tokens=0):
    pricing = MODEL_PRICING.get(model_name)
    if pricing is None:
        return 0.0
    return (input_tokens * pricing["input_per_million"] + output_tokens * pricing["output_per_million"]) / 1_000_000
