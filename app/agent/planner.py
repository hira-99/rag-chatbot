"""Plan generation and validation (Step 19): ask the model to lay out the
whole sequence of tool calls up front, instead of deciding one step at a
time (loop.py's reactive approach).

Not wired into the live chat turn -- app/agent/policies.py's routing plus
the reactive agent loop already cover this app's needs, and a full
plan-then-execute path would add real complexity (replanning after a
failed task, partial-plan UI) for no turn this app actually needs it for.
This exists so the planning pattern itself is implemented and testable,
at the same scope the notebook kept it: Step 19's own executor was "a
stub -- it doesn't call the model to execute tasks."
"""
import json

from pydantic import BaseModel

from app.agent.task_graph import find_cycle
from app.config import MODEL_NAME
from app.llm.client import client
from app.tools.registry import TOOL_REGISTRY


class PlannedTask(BaseModel):
    task_id: str
    tool_name: str
    # A JSON string, not a nested object -- OpenAI's structured-output mode
    # requires every object field to declare additionalProperties: false,
    # which an arbitrary tool-arguments dict can't (confirmed live: a bare
    # `dict` field is rejected with a 400 before the model ever runs).
    arguments_json: str
    depends_on: list[str] = []

    @property
    def arguments(self):
        return json.loads(self.arguments_json)


class Plan(BaseModel):
    tasks: list[PlannedTask]


def create_plan(goal):
    tool_names = ", ".join(TOOL_REGISTRY.keys())
    response = client.chat.completions.parse(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": (
                f"Break the goal into tasks, each calling exactly one tool from: {tool_names}. "
                "Give each task a unique task_id, its arguments as a JSON object string "
                "(arguments_json), and the task_ids it depends on."
            )},
            {"role": "user", "content": goal},
        ],
        response_format=Plan,
    )
    return response.choices[0].message.parsed


def validate_plan(plan):
    """Checks the things a plan can get wrong before execution starts:
    duplicate ids, a dependency on a task that doesn't exist, an unknown
    tool, or a dependency cycle. Returns a list of error strings, empty if
    the plan is valid."""
    errors = []
    tasks_by_id = {}
    for task in plan.tasks:
        if task.task_id in tasks_by_id:
            errors.append(f"duplicate task_id: {task.task_id}")
            continue
        tasks_by_id[task.task_id] = task

    for task in plan.tasks:
        if task.tool_name not in TOOL_REGISTRY:
            errors.append(f"{task.task_id}: unknown tool '{task.tool_name}'")
        for dep in task.depends_on:
            if dep not in tasks_by_id:
                errors.append(f"{task.task_id}: depends on unknown task '{dep}'")

    graph = {task.task_id: {"depends_on": task.depends_on} for task in plan.tasks}
    cycle = find_cycle(graph)
    if cycle:
        errors.append(f"dependency cycle: {' -> '.join(cycle)}")

    return errors
