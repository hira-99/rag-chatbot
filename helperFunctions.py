import tiktoken

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

MODEL_CONTEXT_WINDOWS = {
    "gpt-4.1-mini": 1_048_576,
    "gpt-4.1": 1_048_576,
    "gpt-4o-mini": 128_000,
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

def analyze_tokens(document_text, model):
    """
    Analyze any text.

    Returns:
        - characters
        - words
        - tokens
        - context window
        - percentage of context window used
    """
       
    encoding = tiktoken.encoding_for_model(model)

    tokens = len(encoding.encode(document_text))
    words = len(document_text.split())
    characters = len(document_text)

    context = MODEL_CONTEXT_WINDOWS[model]
    percentage = (tokens / context) * 100

    return {
        "characters": characters,
        "words": words,
        "tokens": tokens,
        "context_window": context,
        "context_percentage": percentage,
    }

def estimate_input_tokens(messages, model):
    """
    Estimate input context size from the messages list sent to OpenAI.

    Pass the full messages array (system + history + new user message).
    """
    text = "\n".join(message["content"] for message in messages)
    return analyze_tokens(text, model)