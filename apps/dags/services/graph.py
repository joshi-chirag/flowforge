"""
Core graph algorithms for DAG validation and execution ordering.
Implements Kahn's Algorithm for topological sort + cycle detection.
"""
from collections import defaultdict, deque


def topological_sort(tasks, dependencies):
    """
    Kahn's Algorithm — returns tasks in valid execution order.
    Raises ValueError if a cycle is detected.

    Args:
        tasks: list of task objects (must have .id attribute)
        dependencies: list of TaskDependency objects (.task_id, .depends_on_id)

    Returns:
        list of tasks in execution order (dependencies first)
    """
    task_map = {task.id: task for task in tasks}
    in_degree = {task.id: 0 for task in tasks}
    adjacency = defaultdict(list)

    for dep in dependencies:
        # depends_on must run BEFORE task
        adjacency[dep.depends_on_id].append(dep.task_id)
        in_degree[dep.task_id] += 1

    # Start with all tasks that have no dependencies
    queue = deque([tid for tid, degree in in_degree.items() if degree == 0])
    ordered = []

    while queue:
        task_id = queue.popleft()
        ordered.append(task_map[task_id])

        for dependent_id in adjacency[task_id]:
            in_degree[dependent_id] -= 1
            if in_degree[dependent_id] == 0:
                queue.append(dependent_id)

    if len(ordered) != len(tasks):
        raise ValueError(
            "Cycle detected in DAG! Tasks cannot have circular dependencies."
        )

    return ordered


def detect_cycle(tasks, dependencies):
    """
    Returns True if the DAG contains a cycle, False otherwise.
    Used for validation before saving a DAG.
    """
    try:
        topological_sort(tasks, dependencies)
        return False
    except ValueError:
        return True


def get_parallel_execution_groups(tasks, dependencies):
    """
    Groups tasks into waves — tasks in the same wave can run in parallel.

    Returns:
        list of lists — each inner list is a group that can run concurrently
    
    Example:
        Wave 0: [Fetch Data]          ← no dependencies
        Wave 1: [Clean, Validate]     ← both depend only on Wave 0
        Wave 2: [Transform]           ← depends on Wave 1
        Wave 3: [Load, Email Report]  ← both depend only on Wave 2
    """
    task_map = {task.id: task for task in tasks}
    in_degree = {task.id: 0 for task in tasks}
    adjacency = defaultdict(list)

    for dep in dependencies:
        adjacency[dep.depends_on_id].append(dep.task_id)
        in_degree[dep.task_id] += 1

    waves = []
    current_wave = [task_map[tid] for tid, deg in in_degree.items() if deg == 0]

    while current_wave:
        waves.append(current_wave)
        next_wave = []
        for task in current_wave:
            for dependent_id in adjacency[task.id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    next_wave.append(task_map[dependent_id])
        current_wave = next_wave

    return waves
