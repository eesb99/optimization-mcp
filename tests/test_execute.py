"""
Tests for optimize_execute tool
"""

import sys
sys.path.insert(0, '/Users/thianseongyee/.claude/mcp-servers/optimization-mcp')

from src.api.execute import optimize_execute


def test_auto_detection_pulp():
    """Test auto-detection selects PuLP for binary variables"""
    result = optimize_execute(
        problem_definition={
            "variables": [
                {"name": "x", "type": "binary"},
                {"name": "y", "type": "binary"}
            ],
            "objective": {
                "coefficients": {"x": 3, "y": 2},
                "sense": "maximize"
            },
            "constraints": [
                {"coefficients": {"x": 1, "y": 1}, "type": "<=", "rhs": 1}
            ]
        },
        auto_detect=True
    )

    print("Test: Auto-Detection PuLP (Binary Variables)")
    print(f"Solver Used: {result.get('solver_used')}")
    print(f"Status: {result['status']}")
    print(f"Solution: {result.get('solution', {})}")

    # Assertions
    assert result["solver_used"] == "pulp"
    assert result["status"] == "optimal"
    assert "solution" in result

    print("✓ Test passed\n")
    return result


def test_auto_detection_cvxpy():
    """Test auto-detection would select CVXPY for quadratic (if implemented)"""
    # For now, with dict format, this will use PuLP
    # Future: Add quadratic coefficient support
    result = optimize_execute(
        problem_definition={
            "variables": [
                {"name": "x", "type": "continuous", "bounds": (0, 10)}
            ],
            "objective": {
                "coefficients": {"x": 1},  # Linear for now
                "sense": "minimize"
            },
            "constraints": [
                {"coefficients": {"x": 1}, "type": ">=", "rhs": 1}
            ]
        },
        auto_detect=True
    )

    print("Test: Auto-Detection CVXPY (Continuous)")
    print(f"Solver Used: {result.get('solver_used')}")
    print(f"Status: {result['status']}")
    print(f"Solution: {result.get('solution', {})}")

    # Assertions
    assert result["solver_used"] in ["pulp", "cvxpy"]  # Either is acceptable for linear
    assert result["status"] == "optimal"

    print("✓ Test passed\n")
    return result


def test_solver_override():
    """Test manual solver selection override"""
    problem_def = {
        "variables": [
            {"name": "x", "type": "continuous", "bounds": (0, 10)},
            {"name": "y", "type": "continuous", "bounds": (0, 10)}
        ],
        "objective": {
            "coefficients": {"x": 5, "y": 3},
            "sense": "maximize"
        },
        "constraints": [
            {"coefficients": {"x": 1, "y": 1}, "type": "<=", "rhs": 12},
            {"coefficients": {"x": 2, "y": 1}, "type": "<=", "rhs": 16}
        ]
    }

    # Test with PuLP
    result_pulp = optimize_execute(
        problem_def,
        auto_detect=False,
        solver_preference="pulp"
    )

    # Test with CVXPY
    result_cvxpy = optimize_execute(
        problem_def,
        auto_detect=False,
        solver_preference="cvxpy"
    )

    print("Test: Solver Override")
    print(f"PuLP Result: {result_pulp.get('solver_used')} - {result_pulp['status']}")
    print(f"CVXPY Result: {result_cvxpy.get('solver_used')} - {result_cvxpy['status']}")

    # Assertions
    assert result_pulp["solver_used"] == "pulp"
    assert result_cvxpy["solver_used"] == "cvxpy"
    assert result_pulp["status"] == "optimal"
    assert result_cvxpy["status"] == "optimal"

    # Both should get similar objective values
    obj_diff = abs(result_pulp.get("objective_value", 0) - result_cvxpy.get("objective_value", 0))
    assert obj_diff < 1.0  # Should agree within tolerance

    print("✓ Test passed\n")
    return result_pulp, result_cvxpy


def test_complex_problem():
    """Test more complex problem with multiple constraints"""
    result = optimize_execute(
        problem_definition={
            "variables": [
                {"name": "x1", "type": "continuous", "bounds": (0, None)},
                {"name": "x2", "type": "continuous", "bounds": (0, None)},
                {"name": "x3", "type": "binary"}
            ],
            "objective": {
                "coefficients": {"x1": 4, "x2": 3, "x3": 5},
                "sense": "maximize"
            },
            "constraints": [
                {"coefficients": {"x1": 2, "x2": 1, "x3": 2}, "type": "<=", "rhs": 20},
                {"coefficients": {"x1": 1, "x2": 2, "x3": 1}, "type": "<=", "rhs": 15},
                {"coefficients": {"x1": 1, "x2": 0, "x3": 0}, "type": "<=", "rhs": 8}
            ]
        }
    )

    print("Test: Complex Problem (3 vars, 3 constraints)")
    print(f"Solver Used: {result.get('solver_used')}")
    print(f"Status: {result['status']}")
    print(f"Objective Value: {result.get('objective_value', 'N/A')}")
    print(f"Solution: {result.get('solution', {})}")

    # Assertions
    assert result["status"] == "optimal"
    assert result["solver_used"] == "pulp"  # Has binary variable
    assert "solution" in result
    assert "x1" in result["solution"]
    assert "x2" in result["solution"]
    assert "x3" in result["solution"]

    print("✓ Test passed\n")
    return result


def test_error_handling():
    """Test error handling for invalid problem definitions"""
    print("Test: Error Handling")

    # Test 1: Empty variables
    result1 = optimize_execute(
        problem_definition={
            "variables": [],
            "objective": {"coefficients": {}, "sense": "maximize"}
        }
    )
    assert result1["status"] == "error"
    print("  ✓ Empty variables caught")

    # Test 2: Missing objective
    result2 = optimize_execute(
        problem_definition={
            "variables": [{"name": "x", "type": "continuous"}]
        }
    )
    assert result2["status"] == "error"
    print("  ✓ Missing objective caught")

    # Test 3: Invalid variable type
    result3 = optimize_execute(
        problem_definition={
            "variables": [{"name": "x", "type": "invalid_type"}],
            "objective": {"coefficients": {"x": 1}, "sense": "maximize"}
        }
    )
    assert result3["status"] == "error"
    print("  ✓ Invalid variable type caught")

    # Test 4: Invalid solver preference
    result4 = optimize_execute(
        problem_definition={
            "variables": [{"name": "x", "type": "continuous"}],
            "objective": {"coefficients": {"x": 1}, "sense": "maximize"}
        },
        solver_preference="invalid_solver"
    )
    assert result4["status"] == "error"
    print("  ✓ Invalid solver preference caught")

    print("✓ All error tests passed\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Running Execute Tool Tests")
    print("=" * 60 + "\n")

    test_auto_detection_pulp()
    test_auto_detection_cvxpy()
    test_solver_override()
    test_complex_problem()
    test_error_handling()

    print("=" * 60)
    print("All execute tests passed!")
    print("=" * 60)
