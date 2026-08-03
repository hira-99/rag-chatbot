def create_initial_state():
    return {
        "messages": [
            {
                "role": "system",
                "content": "You are an Assistant.",
            }
        ],
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "total_cost": 0,
        },
    }
