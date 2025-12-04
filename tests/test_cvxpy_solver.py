"""
Tests for CVXPY Solver
"""

import sys
sys.path.insert(0, '/Users/thianseongyee/.claude/mcp-servers/optimization-mcp')

import numpy as np

try:
    import cvxpy as cp
    from src.solvers.cvxpy_solver import CVXPYSolver
    from src.solvers.base_solver import ObjectiveSense
    CVXPY_AVAILABLE = True
except ImportError:
    CVXPY_AVAILABLE = False
    print("CVXPY not available - skipping tests")


def test_cvxpy_linear_programming():
    """Test basic LP with CVXPY"""
    if not CVXPY_AVAILABLE:
        print("CVXPY not installed - skipping test")
        return

    solver = CVXPYSolver(problem_type="LP")

    # Create variables
    variables = solver.create_variables(
        names=["x", "y"],
        var_type="continuous"
    )

    # Objective: maximize 3x + 2y
    obj_expr = 3 * variables["x"] + 2 * variables["y"]
    solver.set_objective(obj_expr, ObjectiveSense.MAXIMIZE)

    # Constraints:
    # x + y <= 10
    # 2x + y <= 15
    # x >= 0, y >= 0
    solver.add_constraint(variables["x"] + variables["y"] <= 10)
    solver.add_constraint(2 * variables["x"] + variables["y"] <= 15)
    solver.add_constraint(variables["x"] >= 0)
    solver.add_constraint(variables["y"] >= 0)

    # Solve
    status = solver.solve()

    print("Test: CVXPY Linear Programming")
    print(f"Status: {status.value}")
    print(f"Objective Value: {solver.get_objective_value():.2f}")
    print(f"Solution: {solver.get_solution()}")
    print(f"Problem Info: {solver.get_problem_info()}")

    # Assertions
    assert solver.is_optimal()
    assert solver.get_objective_value() > 0
    solution = solver.get_solution()
    assert "x" in solution
    assert "y" in solution

    print("✓ Test passed\n")
    return solver


def test_cvxpy_quadratic_programming():
    """Test QP with CVXPY (portfolio-like problem)"""
    if not CVXPY_AVAILABLE:
        print("CVXPY not installed - skipping test")
        return

    solver = CVXPYSolver(problem_type="QP")

    # Create variables (portfolio weights)
    variables = solver.create_variables(
        names=["w1", "w2", "w3"],
        var_type="continuous"
    )

    # Objective: minimize variance (quadratic)
    # Simplified: minimize w1^2 + w2^2 + w3^2 + 0.5*w1*w2
    w1, w2, w3 = variables["w1"], variables["w2"], variables["w3"]
    obj_expr = cp.quad_form(
        cp.hstack([w1, w2, w3]),
        np.array([[1.0, 0.25, 0], [0.25, 1.0, 0], [0, 0, 1.0]])
    )
    solver.set_objective(obj_expr, ObjectiveSense.MINIMIZE)

    # Constraints:
    # w1 + w2 + w3 = 1 (full investment)
    # w1, w2, w3 >= 0 (no short selling)
    # Expected return: 0.1*w1 + 0.08*w2 + 0.12*w3 >= 0.09
    solver.add_constraint(w1 + w2 + w3 == 1)
    solver.add_constraint(w1 >= 0)
    solver.add_constraint(w2 >= 0)
    solver.add_constraint(w3 >= 0)
    solver.add_constraint(0.1*w1 + 0.08*w2 + 0.12*w3 >= 0.09)

    # Solve
    status = solver.solve()

    print("Test: CVXPY Quadratic Programming")
    print(f"Status: {status.value}")
    print(f"Objective Value (variance): {solver.get_objective_value():.4f}")
    solution = solver.get_solution()
    print(f"Portfolio Weights: w1={solution['w1']:.3f}, w2={solution['w2']:.3f}, w3={solution['w3']:.3f}")
    print(f"Sum of weights: {sum(solution.values()):.3f}")

    # Assertions
    assert solver.is_optimal() or solver.is_feasible()
    assert abs(sum(solution.values()) - 1.0) < 0.01  # Weights sum to 1
    assert all(w >= -0.01 for w in solution.values())  # Non-negative

    print("✓ Test passed\n")
    return solver


def test_cvxpy_with_bounds():
    """Test CVXPY with variable bounds"""
    if not CVXPY_AVAILABLE:
        print("CVXPY not installed - skipping test")
        return

    solver = CVXPYSolver(problem_type="LP")

    # Create variables with bounds
    variables = solver.create_variables(
        names=["x", "y", "z"],
        var_type="continuous",
        bounds={
            "x": (0, 10),  # 0 <= x <= 10
            "y": (5, 15),  # 5 <= y <= 15
            "z": (0, None)  # z >= 0
        }
    )

    # Objective: minimize x + 2y + 3z
    obj_expr = variables["x"] + 2*variables["y"] + 3*variables["z"]
    solver.set_objective(obj_expr, ObjectiveSense.MINIMIZE)

    # Constraint: x + y + z >= 20
    solver.add_constraint(variables["x"] + variables["y"] + variables["z"] >= 20)

    # Solve
    status = solver.solve()

    print("Test: CVXPY with Variable Bounds")
    print(f"Status: {status.value}")
    print(f"Objective Value: {solver.get_objective_value():.2f}")
    solution = solver.get_solution()
    print(f"Solution: x={solution['x']:.2f}, y={solution['y']:.2f}, z={solution['z']:.2f}")

    # Assertions
    assert solver.is_optimal()
    # Check bounds are respected (with small tolerance for numerical precision)
    assert -0.01 <= solution['x'] <= 10.01
    assert 4.99 <= solution['y'] <= 15.01
    assert solution['z'] >= -0.01
    # Check constraint
    assert solution['x'] + solution['y'] + solution['z'] >= 19.99

    print("✓ Test passed\n")
    return solver


def test_cvxpy_infeasible_problem():
    """Test CVXPY with infeasible problem"""
    if not CVXPY_AVAILABLE:
        print("CVXPY not installed - skipping test")
        return

    solver = CVXPYSolver(problem_type="LP")

    # Create variables
    variables = solver.create_variables(
        names=["x", "y"],
        var_type="continuous"
    )

    # Objective
    obj_expr = variables["x"] + variables["y"]
    solver.set_objective(obj_expr, ObjectiveSense.MAXIMIZE)

    # Contradictory constraints
    solver.add_constraint(variables["x"] + variables["y"] <= 5)  # Sum <= 5
    solver.add_constraint(variables["x"] >= 10)  # x >= 10 (impossible with first constraint)
    solver.add_constraint(variables["y"] >= 0)

    # Solve
    status = solver.solve()

    print("Test: CVXPY Infeasible Problem")
    print(f"Status: {status.value}")

    # Assertions
    assert not solver.is_optimal()
    assert not solver.is_feasible()

    print("✓ Test passed (correctly detected infeasibility)\n")
    return solver


def test_cvxpy_binary_variables():
    """Test CVXPY with binary variables"""
    if not CVXPY_AVAILABLE:
        print("CVXPY not installed - skipping test")
        return

    solver = CVXPYSolver(problem_type="LP")

    # Create binary variables (knapsack-like problem)
    variables = solver.create_variables(
        names=["item1", "item2", "item3"],
        var_type="binary"
    )

    # Objective: maximize value
    # Values: 60, 100, 120
    obj_expr = 60*variables["item1"] + 100*variables["item2"] + 120*variables["item3"]
    solver.set_objective(obj_expr, ObjectiveSense.MAXIMIZE)

    # Constraint: weight limit
    # Weights: 10, 20, 30; Capacity: 50
    solver.add_constraint(
        10*variables["item1"] + 20*variables["item2"] + 30*variables["item3"] <= 50
    )

    # Solve
    status = solver.solve(verbose=False)

    print("Test: CVXPY Binary Variables (Knapsack)")
    print(f"Status: {status.value}")
    print(f"Objective Value: {solver.get_objective_value():.0f}")
    solution = solver.get_solution()
    print(f"Items selected: {solution}")

    # Assertions
    assert solver.is_optimal()
    # All values should be 0 or 1 (binary)
    for value in solution.values():
        assert value < 0.01 or value > 0.99  # Close to 0 or 1

    print("✓ Test passed\n")
    return solver


def test_cvxpy_vs_pulp_comparison():
    """Compare CVXPY and PuLP on same LP problem"""
    if not CVXPY_AVAILABLE:
        print("CVXPY not installed - skipping test")
        return

    # Import PuLP solver
    from src.solvers.pulp_solver import PuLPSolver
    import pulp as pl

    # Same problem in both solvers
    # Maximize 3x + 4y
    # Subject to: x + 2y <= 14, 3x - y >= 0, x - y <= 2, x,y >= 0

    # === CVXPY ===
    cvxpy_solver = CVXPYSolver(problem_type="LP")
    cv_vars = cvxpy_solver.create_variables(["x", "y"], "continuous")
    cvxpy_solver.set_objective(
        3*cv_vars["x"] + 4*cv_vars["y"],
        ObjectiveSense.MAXIMIZE
    )
    cvxpy_solver.add_constraint(cv_vars["x"] + 2*cv_vars["y"] <= 14)
    cvxpy_solver.add_constraint(3*cv_vars["x"] - cv_vars["y"] >= 0)
    cvxpy_solver.add_constraint(cv_vars["x"] - cv_vars["y"] <= 2)
    cvxpy_solver.add_constraint(cv_vars["x"] >= 0)
    cvxpy_solver.add_constraint(cv_vars["y"] >= 0)
    cvxpy_solver.solve()

    # === PuLP ===
    pulp_solver = PuLPSolver(problem_name="comparison")
    pl_vars = pulp_solver.create_variables(["x", "y"], "continuous")
    pulp_solver.set_objective(
        3*pl_vars["x"] + 4*pl_vars["y"],
        ObjectiveSense.MAXIMIZE
    )
    pulp_solver.add_constraint(pl_vars["x"] + 2*pl_vars["y"] <= 14)
    pulp_solver.add_constraint(3*pl_vars["x"] - pl_vars["y"] >= 0)
    pulp_solver.add_constraint(pl_vars["x"] - pl_vars["y"] <= 2)
    pulp_solver.solve()

    print("Test: CVXPY vs PuLP Comparison")
    print(f"CVXPY Objective: {cvxpy_solver.get_objective_value():.2f}")
    print(f"PuLP Objective: {pulp_solver.get_objective_value():.2f}")
    print(f"CVXPY Solution: {cvxpy_solver.get_solution()}")
    print(f"PuLP Solution: {pulp_solver.get_solution()}")

    # Assertions - should get same objective value (within tolerance)
    cvxpy_obj = cvxpy_solver.get_objective_value()
    pulp_obj = pulp_solver.get_objective_value()
    assert abs(cvxpy_obj - pulp_obj) < 0.1  # Close enough

    print("✓ Test passed (solvers agree)\n")
    return cvxpy_solver, pulp_solver


if __name__ == "__main__":
    if not CVXPY_AVAILABLE:
        print("=" * 60)
        print("CVXPY not installed!")
        print("Install with: pip install cvxpy")
        print("=" * 60)
        sys.exit(1)

    print("=" * 60)
    print("Running CVXPY Solver Tests")
    print("=" * 60 + "\n")

    test_cvxpy_linear_programming()
    test_cvxpy_quadratic_programming()
    test_cvxpy_with_bounds()
    test_cvxpy_infeasible_problem()
    test_cvxpy_binary_variables()
    test_cvxpy_vs_pulp_comparison()

    print("=" * 60)
    print("All CVXPY tests passed!")
    print("=" * 60)
