"""Safe AST-based calculator tool.

Evaluates arithmetic without Python's eval() -- the AST is walked node by
node, and only numeric literals plus a fixed set of operators are allowed
(Step 16's pattern). Anything else (names, calls, attribute access, ...)
raises instead of running.
"""
import ast
import operator

from pydantic import BaseModel, Field

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


class CalculatorInput(BaseModel):
    expression: str = Field(description="An arithmetic expression, e.g. '12 * (4 + 3)'")


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"unsupported expression node: {ast.dump(node)}")


def calculate(expression: str):
    try:
        tree = ast.parse(expression, mode="eval")
        return {"result": _eval_node(tree.body)}
    except Exception as exc:
        return {"error": f"Could not evaluate '{expression}': {exc}"}
