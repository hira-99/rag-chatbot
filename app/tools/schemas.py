"""Model-facing tool schema builders -- converts a Pydantic input model
into the OpenAI tool-calling schema format."""


def build_tool_schema(name, description, input_model):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": input_model.model_json_schema(),
        },
    }
