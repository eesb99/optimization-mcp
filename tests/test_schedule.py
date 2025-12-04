"""
Tests for optimize_schedule tool
"""

import sys
sys.path.insert(0, '/Users/thianseongyee/.claude/mcp-servers/optimization-mcp')

from src.api.schedule import optimize_schedule


def test_simple_sequential_schedule():
    """Test simple 3-task sequential schedule"""
    result = optimize_schedule(
        tasks=[
            {
                "name": "design",
                "duration": 5,
                "value": 100,
                "dependencies": []
            },
            {
                "name": "build",
                "duration": 10,
                "value": 200,
                "dependencies": ["design"]  # Must finish design first
            },
            {
                "name": "test",
                "duration": 3,
                "value": 50,
                "dependencies": ["build"]  # Must finish build first
            }
        ],
        resources={
            "workers": {"total": 5}
        },
        time_horizon=30,
        optimization_objective="minimize_makespan"
    )

    print("Test: Simple Sequential Schedule")
    print(f"Status: {result['status']}")
    print(f"Makespan: {result.get('makespan', 'N/A')}")
    print(f"Schedule: {result.get('schedule', {})}")
    print(f"Critical Path: {result.get('critical_path', [])}")

    # Assertions
    assert result["status"] == "optimal"
    assert result["makespan"] == 18  # 5 + 10 + 3
    assert result["schedule"]["design"] == 0
    assert result["schedule"]["build"] >= 5  # After design
    assert result["schedule"]["test"] >= 15  # After build
    assert result["critical_path"] == ["design", "build", "test"]

    print("✓ Test passed\n")
    return result


def test_parallel_tasks():
    """Test parallel task scheduling"""
    result = optimize_schedule(
        tasks=[
            {
                "name": "task_a",
                "duration": 5,
                "value": 100,
                "dependencies": [],
                "resources": {"workers": 2}
            },
            {
                "name": "task_b",
                "duration": 5,
                "value": 100,
                "dependencies": [],
                "resources": {"workers": 2}
            },
            {
                "name": "task_c",
                "duration": 3,
                "value": 50,
                "dependencies": ["task_a", "task_b"],  # After both A and B
                "resources": {"workers": 1}
            }
        ],
        resources={
            "workers": {"total": 4}  # Can do A and B in parallel
        },
        time_horizon=20,
        optimization_objective="minimize_makespan"
    )

    print("Test: Parallel Tasks")
    print(f"Status: {result['status']}")
    print(f"Makespan: {result.get('makespan', 'N/A')}")
    print(f"Schedule: {result.get('schedule', {})}")

    # Assertions
    assert result["status"] == "optimal"
    # A and B can run in parallel (both start at 0), then C
    assert result["makespan"] == 8  # max(5, 5) + 3
    assert result["schedule"]["task_a"] == 0
    assert result["schedule"]["task_b"] == 0
    assert result["schedule"]["task_c"] >= 5

    print("✓ Test passed\n")
    return result


def test_resource_constrained_schedule():
    """Test scheduling with limited resources"""
    result = optimize_schedule(
        tasks=[
            {"name": "task_a", "duration": 4, "value": 100, "resources": {"machines": 2}},
            {"name": "task_b", "duration": 4, "value": 100, "resources": {"machines": 2}},
            {"name": "task_c", "duration": 4, "value": 100, "resources": {"machines": 1}}
        ],
        resources={
            "machines": {"total": 3}  # Can't do all tasks in parallel
        },
        time_horizon=20,
        optimization_objective="minimize_makespan"
    )

    print("Test: Resource-Constrained Schedule")
    print(f"Status: {result['status']}")
    print(f"Makespan: {result.get('makespan', 'N/A')}")
    print(f"Schedule: {result.get('schedule', {})}")
    print(f"Resource Usage Sample:")
    if "resource_usage" in result and "machines" in result["resource_usage"]:
        for entry in result["resource_usage"]["machines"][:8]:
            print(f"  Time {entry['time']}: {entry['used']}/{entry['available']} machines ({entry['utilization_pct']:.0f}%)")

    # Assertions
    assert result["status"] == "optimal"
    # With 3 machines total, can't run A+B in parallel (need 4)
    # Optimal: A+C in parallel (3 machines), then B
    # or B+C in parallel, then A
    assert result["makespan"] <= 8  # Should be 8 or better

    print("✓ Test passed\n")
    return result


def test_deadline_constraint():
    """Test scheduling with deadline constraints"""
    result = optimize_schedule(
        tasks=[
            {"name": "task_a", "duration": 5, "value": 100},
            {"name": "task_b", "duration": 8, "value": 200},
            {"name": "task_c", "duration": 3, "value": 50}
        ],
        resources={"workers": {"total": 10}},
        time_horizon=20,
        constraints=[
            {"type": "deadline", "task": "task_b", "time": 10}  # task_b must finish by time 10
        ],
        optimization_objective="minimize_makespan"
    )

    print("Test: Deadline Constraint")
    print(f"Status: {result['status']}")
    print(f"Schedule: {result.get('schedule', {})}")

    # Assertions
    assert result["status"] == "optimal"
    # task_b starts + 8 <= 10, so task_b must start by time 2
    task_b_start = result["schedule"]["task_b"]
    assert task_b_start + 8 <= 10

    print("✓ Test passed\n")
    return result


def test_maximize_value_objective():
    """Test maximizing value instead of minimizing makespan"""
    result = optimize_schedule(
        tasks=[
            {"name": "high_value", "duration": 5, "value": 1000},
            {"name": "low_value_a", "duration": 2, "value": 50},
            {"name": "low_value_b", "duration": 2, "value": 50},
            {"name": "low_value_c", "duration": 2, "value": 50}
        ],
        resources={"capacity": {"total": 100}},
        time_horizon=6,  # Limited time - can't do everything
        optimization_objective="maximize_value"
    )

    print("Test: Maximize Value Objective")
    print(f"Status: {result['status']}")
    print(f"Total Value: {result.get('total_value', 'N/A')}")
    print(f"Schedule: {result.get('schedule', {})}")

    # Assertions
    assert result["status"] == "optimal"
    # Should prioritize high_value task
    assert "high_value" in result["schedule"]
    assert result["total_value"] >= 1000  # At least the high value task

    print("✓ Test passed\n")
    return result


def test_complex_dependencies():
    """Test complex dependency graph"""
    result = optimize_schedule(
        tasks=[
            {"name": "A", "duration": 3, "value": 100, "dependencies": []},
            {"name": "B", "duration": 4, "value": 100, "dependencies": []},
            {"name": "C", "duration": 2, "value": 100, "dependencies": ["A"]},
            {"name": "D", "duration": 5, "value": 100, "dependencies": ["A", "B"]},  # After both A and B
            {"name": "E", "duration": 3, "value": 100, "dependencies": ["C", "D"]}   # After both C and D
        ],
        resources={"workers": {"total": 10}},
        time_horizon=30,
        optimization_objective="minimize_makespan"
    )

    print("Test: Complex Dependencies")
    print(f"Status: {result['status']}")
    print(f"Makespan: {result.get('makespan', 'N/A')}")
    print(f"Schedule: {result.get('schedule', {})}")
    print(f"Critical Path: {result.get('critical_path', [])}")
    print("\nTask Details:")
    for task in result.get("tasks", []):
        cp_marker = " [CRITICAL]" if task["on_critical_path"] else ""
        print(f"  {task['name']}: start={task['start_time']}, end={task['end_time']}{cp_marker}")

    # Assertions
    assert result["status"] == "optimal"
    # Verify dependencies respected
    assert result["schedule"]["C"] >= result["schedule"]["A"] + 3  # C after A
    assert result["schedule"]["D"] >= result["schedule"]["A"] + 3  # D after A
    assert result["schedule"]["D"] >= result["schedule"]["B"] + 4  # D after B
    assert result["schedule"]["E"] >= result["schedule"]["C"] + 2  # E after C
    assert result["schedule"]["E"] >= result["schedule"]["D"] + 5  # E after D

    print("✓ Test passed\n")
    return result


if __name__ == "__main__":
    print("=" * 60)
    print("Running Task Scheduling Tests")
    print("=" * 60 + "\n")

    test_simple_sequential_schedule()
    test_parallel_tasks()
    test_resource_constrained_schedule()
    test_deadline_constraint()
    test_maximize_value_objective()
    test_complex_dependencies()

    print("=" * 60)
    print("All scheduling tests passed!")
    print("=" * 60)
