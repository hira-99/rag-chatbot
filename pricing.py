MODEL_PRICING = {
    "gpt-4.1-mini": {
        "input": 0.40,      # USD per 1M input tokens
        "output": 1.60,     # USD per 1M output tokens
    },
    "gpt-4.1": {
        "input": 2.00,
        "output": 8.00,
    },
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60,
    },
}

def calculate_cost(model, input_tokens, output_tokens):
    pricing = MODEL_PRICING[model]

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    total_cost = input_cost + output_cost

    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
    }