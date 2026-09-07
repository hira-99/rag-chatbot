"""Task dependency graph: readiness, ordering, cycle detection (Step 19)."""


def find_cycle(tasks):
    """tasks: {task_id: {"depends_on": [task_id, ...]}}. Returns a list of
    task_ids forming a cycle, or None if the graph is acyclic."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {task_id: WHITE for task_id in tasks}
    path = []

    def visit(task_id):
        color[task_id] = GRAY
        path.append(task_id)
        for dep in tasks[task_id]["depends_on"]:
            if dep not in tasks:
                continue
            if color[dep] == GRAY:
                return path[path.index(dep):] + [dep]
            if color[dep] == WHITE:
                cycle = visit(dep)
                if cycle:
                    return cycle
        path.pop()
        color[task_id] = BLACK
        return None

    for task_id in tasks:
        if color[task_id] == WHITE:
            cycle = visit(task_id)
            if cycle:
                return cycle
    return None


def ready_tasks(tasks, completed):
    """Tasks whose dependencies are all in `completed` and that aren't
    themselves already completed -- a task becomes ready the moment every
    task it depends on has finished."""
    return [
        task_id for task_id, task in tasks.items()
        if task_id not in completed and all(dep in completed for dep in task["depends_on"])
    ]
