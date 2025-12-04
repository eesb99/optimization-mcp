"""
Task Scheduling Optimization Tool

optimize_schedule: Optimize task scheduling with dependencies and resource constraints.

Use cases:
- Project scheduling (RCPSP - Resource-Constrained Project Scheduling)
- Job shop scheduling
- Task prioritization with deadlines
"""

from typing import Dict, List, Any, Optional
import pulp as pl

from ..solvers.pulp_solver import PuLPSolver
from ..solvers.base_solver import ObjectiveSense
from ..integration.monte_carlo import MonteCarloIntegration
from ..integration.data_converters import DataConverter


def optimize_schedule(
    tasks: List[Dict[str, Any]],
    resources: Dict[str, Dict[str, float]],
    time_horizon: int,
    constraints: Optional[List[Dict[str, Any]]] = None,
    optimization_objective: str = "minimize_makespan",
    monte_carlo_integration: Optional[Dict[str, Any]] = None,
    solver_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Task scheduling with dependencies and resource constraints.

    Args:
        tasks: List of tasks with:
              - name: Task identifier
              - duration: Task duration (time units)
              - value: Task value/priority (for maximize_value objective)
              - dependencies: List of prerequisite task names (optional)
              - resources: Dict of resource requirements per time unit (optional)
        resources: Available resources per time period:
                  - {"workers": {"total": 10}, "machines": {"total": 5}}
        time_horizon: Total scheduling window (time units)
        constraints: Optional temporal constraints:
                    - {type: "deadline", task: "task_a", time: 20}
                    - {type: "release", task: "task_b", time: 5}
                    - {type: "parallel_limit", limit: 3}  # Max 3 tasks in parallel
        optimization_objective: "minimize_makespan" or "maximize_value"
        monte_carlo_integration: Optional MC for uncertain durations/values
        solver_options: Optional solver settings

    Returns:
        Dict with:
        - status: "optimal", "infeasible", etc.
        - schedule: Dict mapping task → start_time
        - makespan: Total completion time
        - resource_usage: Resource utilization over time
        - critical_path: Sequence of tasks determining makespan
        - monte_carlo_compatible: MC output

    Example:
        result = optimize_schedule(
            tasks=[
                {
                    "name": "design",
                    "duration": 5,
                    "value": 100,
                    "dependencies": [],
                    "resources": {"workers": 2}
                },
                {
                    "name": "build",
                    "duration": 10,
                    "value": 200,
                    "dependencies": ["design"],  # Must finish design first
                    "resources": {"workers": 3, "machines": 1}
                },
                {
                    "name": "test",
                    "duration": 3,
                    "value": 50,
                    "dependencies": ["build"],
                    "resources": {"workers": 1}
                }
            ],
            resources={
                "workers": {"total": 5},
                "machines": {"total": 2}
            },
            time_horizon=30,
            optimization_objective="minimize_makespan"
        )
    """
    # Validate inputs
    _validate_schedule_inputs(tasks, resources, time_horizon, optimization_objective)

    # Extract solver options
    solver_opts = solver_options or {}
    time_limit = solver_opts.get("time_limit", None)
    verbose = solver_opts.get("verbose", False)

    # Process task properties (with MC integration if provided)
    task_data = _process_task_data(tasks, monte_carlo_integration)

    # Create solver
    solver = PuLPSolver(problem_name="task_scheduling")

    # Build task-time binary variables
    # x[task, t] = 1 if task starts at time t
    var_names = []
    task_names = [task["name"] for task in tasks]

    for task_name in task_names:
        task_duration = task_data[task_name]["duration"]
        # Task can start from time 0 to (time_horizon - duration)
        max_start = time_horizon - task_duration
        for t in range(max_start + 1):
            var_names.append(f"{task_name}_t{t}")

    variables = solver.create_variables(
        names=var_names,
        var_type="binary"
    )

    # Helper function to get variable
    def get_var(task: str, time: int) -> Any:
        return variables.get(f"{task}_t{time}", 0)

    # Set objective FIRST (required by PuLP before adding constraints)
    if optimization_objective == "minimize_makespan":
        # Create makespan variable
        makespan_var = pl.LpVariable("makespan", lowBound=0, cat=pl.LpContinuous)
        solver.set_objective(makespan_var, ObjectiveSense.MINIMIZE)

    elif optimization_objective == "maximize_value":
        # Maximize total value of completed tasks
        total_value = pl.lpSum([
            task_data[task_name]["value"] * pl.lpSum([
                get_var(task_name, t)
                for t in range(time_horizon - task_data[task_name]["duration"] + 1)
            ])
            for task_name in task_names
        ])
        solver.set_objective(total_value, ObjectiveSense.MAXIMIZE)

    else:
        return {
            "status": "error",
            "error": f"Invalid optimization_objective: {optimization_objective}",
            "message": "Must be 'minimize_makespan' or 'maximize_value'"
        }

    # Now add constraints
    # Constraint 1: Each task starts exactly once
    for task_name in task_names:
        task_duration = task_data[task_name]["duration"]
        max_start = time_horizon - task_duration
        task_start_vars = [get_var(task_name, t) for t in range(max_start + 1)]
        solver.add_constraint(
            pl.lpSum(task_start_vars) == 1,
            name=f"start_once_{task_name}"
        )

    # Constraint 2: Precedence constraints (dependencies)
    for task in tasks:
        task_name = task["name"]
        dependencies = task.get("dependencies", [])

        for dep_task in dependencies:
            # dep_task must finish before task_name starts
            dep_duration = task_data[dep_task]["duration"]

            # Calculate start time for each task
            # start_time = sum(t * x[task,t] for all t)
            task_start = pl.lpSum([
                t * get_var(task_name, t)
                for t in range(time_horizon - task_data[task_name]["duration"] + 1)
            ])

            dep_start = pl.lpSum([
                t * get_var(dep_task, t)
                for t in range(time_horizon - dep_duration + 1)
            ])

            # task starts >= dep starts + dep duration
            solver.add_constraint(
                task_start >= dep_start + dep_duration,
                name=f"precedence_{dep_task}_to_{task_name}"
            )

    # Constraint 3: Resource constraints
    if resources:
        for resource_name, resource_spec in resources.items():
            total_available = resource_spec["total"]

            # For each time t, sum of resource usage <= available
            for t in range(time_horizon):
                resource_usage_at_t = 0

                for task in tasks:
                    task_name = task["name"]
                    task_duration = task_data[task_name]["duration"]
                    task_resources = task.get("resources", {})
                    task_resource_req = task_resources.get(resource_name, 0)

                    if task_resource_req > 0:
                        # Task uses resources during [start, start+duration)
                        # If task starts at s, it's active at time t if s <= t < s+duration
                        for s in range(time_horizon - task_duration + 1):
                            if s <= t < s + task_duration:
                                # If task starts at s, it's using resources at t
                                resource_usage_at_t += task_resource_req * get_var(task_name, s)

                solver.add_constraint(
                    resource_usage_at_t <= total_available,
                    name=f"resource_{resource_name}_t{t}"
                )

    # Constraint 4: Additional temporal constraints
    if constraints:
        for constraint in constraints:
            ctype = constraint.get("type")

            if ctype == "deadline":
                # Task must finish by deadline
                task_name = constraint["task"]
                deadline = constraint["time"]
                task_duration = task_data[task_name]["duration"]

                # start + duration <= deadline
                task_start = pl.lpSum([
                    t * get_var(task_name, t)
                    for t in range(time_horizon - task_duration + 1)
                ])
                solver.add_constraint(
                    task_start + task_duration <= deadline,
                    name=f"deadline_{task_name}"
                )

            elif ctype == "release":
                # Task cannot start before release time
                task_name = constraint["task"]
                release_time = constraint["time"]
                task_duration = task_data[task_name]["duration"]

                # Only allow starts at t >= release_time
                for t in range(min(release_time, time_horizon - task_duration + 1)):
                    solver.add_constraint(
                        get_var(task_name, t) == 0,
                        name=f"release_{task_name}_t{t}"
                    )

            elif ctype == "parallel_limit":
                # Maximum number of tasks in parallel
                max_parallel = constraint["limit"]

                for t in range(time_horizon):
                    # Count tasks active at time t
                    tasks_active_at_t = 0
                    for task_name in task_names:
                        task_duration = task_data[task_name]["duration"]
                        for s in range(time_horizon - task_duration + 1):
                            if s <= t < s + task_duration:
                                tasks_active_at_t += get_var(task_name, s)

                    solver.add_constraint(
                        tasks_active_at_t <= max_parallel,
                        name=f"parallel_limit_t{t}"
                    )

    # Add makespan constraints (if minimizing makespan)
    if optimization_objective == "minimize_makespan":
        # Makespan >= end time of each task
        # Note: makespan_var was already created and objective was set earlier
        for task_name in task_names:
            task_duration = task_data[task_name]["duration"]
            task_end = pl.lpSum([
                (t + task_duration) * get_var(task_name, t)
                for t in range(time_horizon - task_duration + 1)
            ])
            solver.add_constraint(
                makespan_var >= task_end,
                name=f"makespan_{task_name}"
            )

    # Solve
    try:
        status = solver.solve(time_limit=time_limit, verbose=verbose)
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Solver encountered an error during scheduling"
        }

    # Build result
    result = _build_schedule_result(
        solver,
        task_names,
        task_data,
        time_horizon,
        resources,
        optimization_objective,
        variables
    )

    # Add Monte Carlo compatible output
    if solver.is_feasible():
        mc_output = _create_mc_compatible_output(
            result["schedule"],
            task_data,
            result.get("makespan", 0)
        )
        result["monte_carlo_compatible"] = mc_output

    return result


def _validate_schedule_inputs(
    tasks: List[Dict[str, Any]],
    resources: Dict[str, Dict[str, float]],
    time_horizon: int,
    optimization_objective: str
):
    """Validate scheduling inputs."""
    if not isinstance(tasks, list) or len(tasks) == 0:
        raise ValueError("Tasks list cannot be empty")

    if time_horizon <= 0:
        raise ValueError("Time horizon must be positive")

    valid_objectives = ["minimize_makespan", "maximize_value"]
    if optimization_objective not in valid_objectives:
        raise ValueError(
            f"Invalid optimization_objective: {optimization_objective}. "
            f"Must be one of: {valid_objectives}"
        )

    for i, task in enumerate(tasks):
        if "name" not in task:
            raise ValueError(f"Task {i} missing 'name'")
        if "duration" not in task:
            raise ValueError(f"Task {i} missing 'duration'")
        if task["duration"] <= 0:
            raise ValueError(f"Task {task['name']} duration must be positive")
        if task["duration"] > time_horizon:
            raise ValueError(
                f"Task {task['name']} duration ({task['duration']}) "
                f"exceeds time_horizon ({time_horizon})"
            )


def _process_task_data(
    tasks: List[Dict[str, Any]],
    mc_integration: Optional[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """
    Process task data, incorporating Monte Carlo if provided.

    Args:
        tasks: List of task specifications
        mc_integration: Optional MC integration

    Returns:
        Dict mapping task names to processed data
    """
    task_data = {}

    for task in tasks:
        task_name = task["name"]
        task_data[task_name] = {
            "duration": task["duration"],
            "value": task.get("value", 0),
            "dependencies": task.get("dependencies", []),
            "resources": task.get("resources", {})
        }

    # Override durations/values with MC data if provided
    if mc_integration:
        mode = mc_integration.get("mode", "expected")
        mc_output = mc_integration.get("mc_output")

        if mc_output:
            if mode == "percentile":
                percentile = mc_integration.get("percentile", "p50")
                mc_values = MonteCarloIntegration.extract_percentile_values(
                    mc_output,
                    percentile
                )
                for task_name in task_data.keys():
                    # MC can provide uncertain durations
                    duration_key = f"{task_name}_duration"
                    if duration_key in mc_values:
                        task_data[task_name]["duration"] = int(mc_values[duration_key])

                    # MC can provide uncertain values
                    value_key = f"{task_name}_value"
                    if value_key in mc_values:
                        task_data[task_name]["value"] = mc_values[value_key]

            elif mode == "expected":
                mc_values = MonteCarloIntegration.extract_expected_values(mc_output)
                for task_name in task_data.keys():
                    duration_key = f"{task_name}_duration"
                    if duration_key in mc_values:
                        task_data[task_name]["duration"] = int(mc_values[duration_key])

                    value_key = f"{task_name}_value"
                    if value_key in mc_values:
                        task_data[task_name]["value"] = mc_values[value_key]

    return task_data


def _build_schedule_result(
    solver: PuLPSolver,
    task_names: List[str],
    task_data: Dict[str, Dict[str, Any]],
    time_horizon: int,
    resources: Dict[str, Dict[str, float]],
    optimization_objective: str,
    variables: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build comprehensive scheduling result.

    Args:
        solver: Solved PuLP solver
        task_names: List of task names
        task_data: Processed task data
        time_horizon: Time horizon
        resources: Resource specifications
        optimization_objective: Objective used
        variables: Decision variables

    Returns:
        Scheduling result dictionary
    """
    result = {
        "solver": "pulp",
        "optimization_objective": optimization_objective,
        "status": solver.status.value,
        "is_optimal": solver.is_optimal(),
        "is_feasible": solver.is_feasible(),
        "solve_time_seconds": solver.solve_time
    }

    if not solver.is_feasible():
        result["message"] = _generate_infeasibility_message(
            solver.status.value,
            task_names,
            task_data,
            time_horizon
        )
        return result

    # Extract solution
    solution = solver.get_solution()

    # Decode schedule (find start time for each task)
    schedule = {}
    for task_name in task_names:
        task_duration = task_data[task_name]["duration"]
        max_start = time_horizon - task_duration

        for t in range(max_start + 1):
            var_name = f"{task_name}_t{t}"
            if var_name in solution and solution[var_name] > 0.5:  # Binary variable
                schedule[task_name] = t
                break

    result["schedule"] = schedule

    # Calculate makespan (latest completion time)
    makespan = 0
    for task_name, start_time in schedule.items():
        end_time = start_time + task_data[task_name]["duration"]
        makespan = max(makespan, end_time)

    result["makespan"] = makespan

    # Calculate resource usage over time
    resource_usage = _calculate_resource_usage(
        schedule,
        task_data,
        resources,
        time_horizon
    )
    result["resource_usage"] = resource_usage

    # Identify critical path (sequence determining makespan)
    critical_path = _find_critical_path(schedule, task_data, task_names)
    result["critical_path"] = critical_path

    # Add task details
    task_details = []
    for task_name in task_names:
        start_time = schedule.get(task_name, None)
        if start_time is not None:
            end_time = start_time + task_data[task_name]["duration"]
            task_details.append({
                "name": task_name,
                "start_time": start_time,
                "end_time": end_time,
                "duration": task_data[task_name]["duration"],
                "value": task_data[task_name]["value"],
                "dependencies": task_data[task_name]["dependencies"],
                "on_critical_path": task_name in critical_path
            })

    result["tasks"] = task_details

    # Total value achieved
    if optimization_objective == "maximize_value":
        total_value = sum(task_data[name]["value"] for name in schedule.keys())
        result["total_value"] = total_value

    return result


def _calculate_resource_usage(
    schedule: Dict[str, int],
    task_data: Dict[str, Dict[str, Any]],
    resources: Dict[str, Dict[str, float]],
    time_horizon: int
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Calculate resource utilization over time.

    Args:
        schedule: Task start times
        task_data: Task specifications
        resources: Resource availabilities
        time_horizon: Time horizon

    Returns:
        Dict mapping resource names to time-series usage data
    """
    resource_usage = {}

    for resource_name in resources.keys():
        total_available = resources[resource_name]["total"]
        usage_timeline = []

        for t in range(time_horizon):
            used = 0

            # Sum usage from all active tasks at time t
            for task_name, start_time in schedule.items():
                task_duration = task_data[task_name]["duration"]
                end_time = start_time + task_duration

                # Task active at time t?
                if start_time <= t < end_time:
                    task_resources = task_data[task_name]["resources"]
                    used += task_resources.get(resource_name, 0)

            usage_timeline.append({
                "time": t,
                "used": used,
                "available": total_available,
                "utilization_pct": (used / total_available * 100) if total_available > 0 else 0
            })

        resource_usage[resource_name] = usage_timeline

    return resource_usage


def _find_critical_path(
    schedule: Dict[str, int],
    task_data: Dict[str, Dict[str, Any]],
    task_names: List[str]
) -> List[str]:
    """
    Identify critical path (tasks determining makespan).

    Args:
        schedule: Task start times
        task_data: Task specifications
        task_names: All task names

    Returns:
        List of task names on critical path
    """
    # Find task with latest end time
    latest_end = 0
    last_task = None

    for task_name, start_time in schedule.items():
        end_time = start_time + task_data[task_name]["duration"]
        if end_time > latest_end:
            latest_end = end_time
            last_task = task_name

    if last_task is None:
        return []

    # Trace backward through dependencies
    critical_path = []
    current_task = last_task

    while current_task:
        critical_path.insert(0, current_task)

        # Find predecessor on critical path
        dependencies = task_data[current_task]["dependencies"]
        if not dependencies:
            break

        # Find which dependency finishes latest (is on critical path)
        latest_pred_end = -1
        critical_pred = None

        for dep in dependencies:
            dep_start = schedule.get(dep, 0)
            dep_end = dep_start + task_data[dep]["duration"]

            if dep_end > latest_pred_end:
                latest_pred_end = dep_end
                critical_pred = dep

        current_task = critical_pred

    return critical_path


def _generate_infeasibility_message(
    status: str,
    task_names: List[str],
    task_data: Dict[str, Dict[str, Any]],
    time_horizon: int
) -> str:
    """
    Generate helpful error message for infeasible schedules.

    Args:
        status: Solver status
        task_names: List of tasks
        task_data: Task specifications
        time_horizon: Time horizon

    Returns:
        Helpful error message
    """
    if status == "infeasible":
        # Check if total duration exceeds horizon (for sequential tasks)
        total_duration = sum(task_data[name]["duration"] for name in task_names)

        if total_duration > time_horizon:
            return (
                f"Schedule is infeasible. Total task duration ({total_duration}) "
                f"exceeds time horizon ({time_horizon}). "
                "Consider increasing time_horizon or reducing task durations."
            )
        else:
            return (
                "Schedule is infeasible. Possible causes:\n"
                "- Resource constraints too tight\n"
                "- Deadline constraints impossible to meet\n"
                "- Dependency cycles\n"
                "Try relaxing constraints or increasing time_horizon."
            )
    else:
        return f"Scheduling optimization failed with status: {status}"


def _create_mc_compatible_output(
    schedule: Dict[str, int],
    task_data: Dict[str, Dict[str, Any]],
    makespan: int
) -> Dict[str, Any]:
    """
    Create Monte Carlo compatible output for validation.

    Args:
        schedule: Optimal schedule
        task_data: Task specifications
        makespan: Project completion time

    Returns:
        MC compatible output dict
    """
    # Create assumptions (task durations as uncertain)
    assumptions = []
    for task_name, task_info in task_data.items():
        assumptions.append({
            "name": f"{task_name}_duration",
            "value": task_info["duration"],
            "distribution": {
                "type": "normal",
                "params": {
                    "mean": task_info["duration"],
                    "std": task_info["duration"] * 0.15  # 15% uncertainty
                }
            }
        })

    return {
        "decision_variables": schedule,
        "assumptions": assumptions,
        "outcome_function": f"Project makespan with {len(schedule)} tasks",
        "expected_value": makespan,
        "recommended_next_tool": "validate_reasoning_confidence",
        "recommended_params": {
            "decision_context": f"Task scheduling with {len(schedule)} tasks",
            "assumptions": {
                a["name"]: {
                    "distribution": a["distribution"]["type"],
                    "params": a["distribution"]["params"]
                }
                for a in assumptions
            },
            "success_criteria": {
                "threshold": makespan * 1.10,  # 10% buffer
                "comparison": "<="
            },
            "num_simulations": 10000
        }
    }
