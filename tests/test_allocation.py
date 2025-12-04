"""
Tests for optimize_allocation tool
"""

import sys
sys.path.insert(0, '/Users/thianseongyee/.claude/mcp-servers/optimization-mcp')

from src.api.allocation import optimize_allocation


def test_simple_allocation():
    """Test basic resource allocation"""
    result = optimize_allocation(
        objective={
            "items": [
                {"name": "project_a", "value": 50000},
                {"name": "project_b", "value": 35000},
                {"name": "project_c", "value": 45000}
            ],
            "sense": "maximize"
        },
        resources={
            "budget": {"total": 100000}
        },
        item_requirements=[
            {"name": "project_a", "budget": 25000},
            {"name": "project_b", "budget": 18000},
            {"name": "project_c", "budget": 32000}
        ]
    )

    print("Test: Simple Allocation")
    print(f"Status: {result['status']}")
    print(f"Objective Value: {result.get('objective_value', 'N/A')}")
    print(f"Allocation: {result.get('allocation', {})}")
    print(f"Resource Usage: {result.get('resource_usage', {})}")

    # Assertions
    assert result["status"] == "optimal"
    assert result["is_optimal"] == True
    assert "allocation" in result
    assert "monte_carlo_compatible" in result

    print("✓ Test passed\n")
    return result


def test_infeasible_allocation():
    """Test when item exceeds resources (optimal = select nothing)"""
    result = optimize_allocation(
        objective={
            "items": [
                {"name": "project_a", "value": 50000}
            ],
            "sense": "maximize"
        },
        resources={
            "budget": {"total": 10000}  # Not enough budget
        },
        item_requirements=[
            {"name": "project_a", "budget": 25000}  # Requires more than available
        ]
    )

    print("Test: Item Exceeds Resources")
    print(f"Status: {result['status']}")
    print(f"Objective Value: {result.get('objective_value', 0)}")
    print(f"Allocation: {result.get('allocation', {})}")

    # Correct behavior: optimal solution is to select nothing (objective = 0)
    assert result["status"] == "optimal"
    assert result.get("objective_value", 0) == 0

    print("✓ Test passed\n")
    return result


def test_multi_resource_allocation():
    """Test allocation with multiple resources"""
    result = optimize_allocation(
        objective={
            "items": [
                {"name": "project_a", "value": 100},
                {"name": "project_b", "value": 80},
                {"name": "project_c", "value": 90}
            ],
            "sense": "maximize"
        },
        resources={
            "budget": {"total": 100},
            "time": {"total": 200}
        },
        item_requirements=[
            {"name": "project_a", "budget": 30, "time": 50},
            {"name": "project_b", "budget": 25, "time": 80},
            {"name": "project_c", "budget": 40, "time": 60}
        ]
    )

    print("Test: Multi-Resource Allocation")
    print(f"Status: {result['status']}")
    print(f"Objective Value: {result.get('objective_value', 'N/A')}")
    print(f"Allocation: {result.get('allocation', {})}")
    print(f"Resource Usage: {result.get('resource_usage', {})}")

    assert result["status"] == "optimal"
    assert len(result["resource_usage"]) == 2  # budget and time

    print("✓ Test passed\n")
    return result


def test_multi_objective_two_functions():
    """Test multi-objective optimization with 2 functions"""
    result = optimize_allocation(
        objective={
            "sense": "maximize",
            "functions": [
                {
                    "name": "profit",
                    "items": [
                        {"name": "product_a", "value": 100},
                        {"name": "product_b", "value": 150}
                    ],
                    "weight": 0.7  # 70% weight on profit
                },
                {
                    "name": "sustainability",
                    "items": [
                        {"name": "product_a", "value": 80},
                        {"name": "product_b", "value": 60}
                    ],
                    "weight": 0.3  # 30% weight on sustainability
                }
            ]
        },
        resources={
            "budget": {"total": 50000}
        },
        item_requirements=[
            {"name": "product_a", "budget": 25000},
            {"name": "product_b", "budget": 30000}
        ]
    )

    print("Test: Multi-Objective (2 Functions)")
    print(f"Status: {result['status']}")
    print(f"Objective Value: {result.get('objective_value', 'N/A')}")
    print(f"Allocation: {result.get('allocation', {})}")
    print(f"Objective Breakdown: {result.get('objective_breakdown', {})}")

    # Assertions
    assert result["status"] == "optimal"
    assert result["is_optimal"] == True
    assert "objective_breakdown" in result
    assert len(result["objective_breakdown"]) == 2
    assert "profit" in result["objective_breakdown"]
    assert "sustainability" in result["objective_breakdown"]

    # Verify weights are correct
    assert result["objective_breakdown"]["profit"]["weight"] == 0.7
    assert result["objective_breakdown"]["sustainability"]["weight"] == 0.3

    print("✓ Test passed\n")
    return result


def test_multi_objective_weight_distribution():
    """Test multi-objective with different weight combinations"""
    # Test with 0.5/0.5 balanced weights
    result = optimize_allocation(
        objective={
            "sense": "maximize",
            "functions": [
                {
                    "name": "return",
                    "items": [
                        {"name": "investment_a", "value": 50},
                        {"name": "investment_b", "value": 80}
                    ],
                    "weight": 0.5
                },
                {
                    "name": "risk_reduction",
                    "items": [
                        {"name": "investment_a", "value": 40},
                        {"name": "investment_b", "value": 30}
                    ],
                    "weight": 0.5
                }
            ]
        },
        resources={
            "capital": {"total": 10000}
        },
        item_requirements=[
            {"name": "investment_a", "capital": 5000},
            {"name": "investment_b", "capital": 6000}
        ]
    )

    print("Test: Multi-Objective Weight Distribution (0.5/0.5)")
    print(f"Status: {result['status']}")
    print(f"Objective Value: {result.get('objective_value', 'N/A')}")
    print(f"Objective Breakdown: {result.get('objective_breakdown', {})}")

    assert result["status"] == "optimal"
    assert "objective_breakdown" in result

    # Calculate weighted sum manually and verify
    breakdown = result["objective_breakdown"]
    total_weighted = sum(obj["weighted_value"] for obj in breakdown.values())
    assert abs(total_weighted - result["objective_value"]) < 0.01

    print("✓ Test passed\n")
    return result


def test_multi_objective_validation():
    """Test multi-objective validation errors"""
    print("Test: Multi-Objective Validation")

    # Test 1: Weights don't sum to 1.0
    try:
        optimize_allocation(
            objective={
                "sense": "maximize",
                "functions": [
                    {
                        "name": "func1",
                        "items": [{"name": "item_a", "value": 100}],
                        "weight": 0.6  # 0.6 + 0.5 = 1.1 (invalid)
                    },
                    {
                        "name": "func2",
                        "items": [{"name": "item_b", "value": 50}],
                        "weight": 0.5
                    }
                ]
            },
            resources={"budget": {"total": 1000}},
            item_requirements=[
                {"name": "item_a", "budget": 100},
                {"name": "item_b", "budget": 100}
            ]
        )
        assert False, "Should have raised ValueError for weight sum"
    except ValueError as e:
        assert "must sum to 1.0" in str(e)
        print(f"  ✓ Correctly caught weight sum error: {e}")

    # Test 2: Only 1 function (need at least 2)
    try:
        optimize_allocation(
            objective={
                "sense": "maximize",
                "functions": [
                    {
                        "name": "func1",
                        "items": [{"name": "item_a", "value": 100}],
                        "weight": 1.0
                    }
                ]
            },
            resources={"budget": {"total": 1000}},
            item_requirements=[{"name": "item_a", "budget": 100}]
        )
        assert False, "Should have raised ValueError for single function"
    except ValueError as e:
        assert "at least 2 functions" in str(e)
        print(f"  ✓ Correctly caught single function error: {e}")

    # Test 3: Missing required keys (items missing)
    try:
        optimize_allocation(
            objective={
                "sense": "maximize",
                "functions": [
                    {
                        "name": "func1",
                        # Missing "items"
                        "weight": 0.5
                    },
                    {
                        "name": "func2",
                        "items": [{"name": "item_b", "value": 50}],
                        "weight": 0.5
                    }
                ]
            },
            resources={"budget": {"total": 1000}},
            item_requirements=[
                {"name": "item_a", "budget": 100},
                {"name": "item_b", "budget": 100}
            ]
        )
        assert False, "Should have raised ValueError for missing items"
    except ValueError as e:
        assert "missing required key" in str(e)
        print(f"  ✓ Correctly caught missing key error: {e}")

    print("✓ All validation tests passed\n")


def test_backward_compatibility():
    """Test that single-objective format still works (backward compatibility)"""
    # This should use the same format as test_simple_allocation
    result = optimize_allocation(
        objective={
            "items": [
                {"name": "project_a", "value": 50000},
                {"name": "project_b", "value": 35000}
            ],
            "sense": "maximize"
        },
        resources={
            "budget": {"total": 100000}
        },
        item_requirements=[
            {"name": "project_a", "budget": 25000},
            {"name": "project_b", "budget": 18000}
        ]
    )

    print("Test: Backward Compatibility (Single Objective)")
    print(f"Status: {result['status']}")
    print(f"Objective Value: {result.get('objective_value', 'N/A')}")

    # Should work exactly as before
    assert result["status"] == "optimal"
    assert "allocation" in result
    assert "monte_carlo_compatible" in result
    # Should NOT have objective_breakdown for single objective
    assert "objective_breakdown" not in result

    print("✓ Test passed\n")
    return result


def test_conditional_constraints():
    """Test conditional (if-then) constraints"""
    result = optimize_allocation(
        objective={
            "items": [
                {"name": "project_a", "value": 100},
                {"name": "project_b", "value": 80},
                {"name": "project_c", "value": 60}
            ],
            "sense": "maximize"
        },
        resources={"budget": {"total": 100}},
        item_requirements=[
            {"name": "project_a", "budget": 40},
            {"name": "project_b", "budget": 30},
            {"name": "project_c", "budget": 25}
        ],
        constraints=[
            {
                "type": "conditional",
                "condition_item": "project_a",
                "then_item": "project_b",
                "description": "if_a_then_b"
            }
        ]
    )

    print("Test: Conditional Constraints (If-Then)")
    print(f"Status: {result['status']}")
    print(f"Allocation: {result.get('allocation', {})}")

    # Assertions
    assert result["status"] == "optimal"
    # If project_a is selected (1), then project_b must be selected (1)
    # If project_a is not selected (0), project_b can be anything
    if result["allocation"]["project_a"] == 1:
        assert result["allocation"]["project_b"] == 1

    print("✓ Test passed\n")
    return result


def test_disjunctive_constraints():
    """Test disjunctive (OR) constraints"""
    result = optimize_allocation(
        objective={
            "items": [
                {"name": "option_a", "value": 100},
                {"name": "option_b", "value": 80},
                {"name": "option_c", "value": 90},
                {"name": "option_d", "value": 70}
            ],
            "sense": "maximize"
        },
        resources={"budget": {"total": 100}},
        item_requirements=[
            {"name": "option_a", "budget": 30},
            {"name": "option_b", "budget": 25},
            {"name": "option_c", "budget": 28},
            {"name": "option_d", "budget": 20}
        ],
        constraints=[
            {
                "type": "disjunctive",
                "items": ["option_a", "option_b", "option_c"],
                "min_selected": 2,
                "description": "at_least_2_of_3"
            }
        ]
    )

    print("Test: Disjunctive Constraints (OR - At Least 2)")
    print(f"Status: {result['status']}")
    print(f"Allocation: {result.get('allocation', {})}")

    # Assertions
    assert result["status"] == "optimal"
    # At least 2 of {option_a, option_b, option_c} must be selected
    selected_count = sum([
        result["allocation"]["option_a"],
        result["allocation"]["option_b"],
        result["allocation"]["option_c"]
    ])
    assert selected_count >= 2

    print("✓ Test passed\n")
    return result


def test_mutex_constraints():
    """Test mutual exclusivity (XOR) constraints"""
    result = optimize_allocation(
        objective={
            "items": [
                {"name": "strategy_a", "value": 100},
                {"name": "strategy_b", "value": 110},
                {"name": "strategy_c", "value": 95},
                {"name": "other", "value": 50}
            ],
            "sense": "maximize"
        },
        resources={"budget": {"total": 200}},
        item_requirements=[
            {"name": "strategy_a", "budget": 80},
            {"name": "strategy_b", "budget": 90},
            {"name": "strategy_c", "budget": 75},
            {"name": "other", "budget": 30}
        ],
        constraints=[
            {
                "type": "mutex",
                "items": ["strategy_a", "strategy_b", "strategy_c"],
                "exactly": 1,
                "description": "exactly_one_strategy"
            }
        ]
    )

    print("Test: Mutex Constraints (Exactly One)")
    print(f"Status: {result['status']}")
    print(f"Allocation: {result.get('allocation', {})}")

    # Assertions
    assert result["status"] == "optimal"
    # Exactly 1 of {strategy_a, strategy_b, strategy_c} must be selected
    selected_count = sum([
        result["allocation"]["strategy_a"],
        result["allocation"]["strategy_b"],
        result["allocation"]["strategy_c"]
    ])
    assert selected_count == 1

    print("✓ Test passed\n")
    return result


def test_combined_advanced_constraints():
    """Test combination of advanced constraints"""
    result = optimize_allocation(
        objective={
            "items": [
                {"name": "core_a", "value": 100},
                {"name": "core_b", "value": 95},
                {"name": "addon_1", "value": 50},
                {"name": "addon_2", "value": 45}
            ],
            "sense": "maximize"
        },
        resources={"budget": {"total": 150}},
        item_requirements=[
            {"name": "core_a", "budget": 50},
            {"name": "core_b", "budget": 48},
            {"name": "addon_1", "budget": 25},
            {"name": "addon_2", "budget": 22}
        ],
        constraints=[
            {
                "type": "mutex",
                "items": ["core_a", "core_b"],
                "exactly": 1,
                "description": "pick_one_core"
            },
            {
                "type": "conditional",
                "condition_item": "core_a",
                "then_item": "addon_1",
                "description": "if_core_a_then_addon_1"
            },
            {
                "type": "disjunctive",
                "items": ["addon_1", "addon_2"],
                "min_selected": 1,
                "description": "at_least_one_addon"
            }
        ]
    )

    print("Test: Combined Advanced Constraints")
    print(f"Status: {result['status']}")
    print(f"Allocation: {result.get('allocation', {})}")

    # Assertions
    assert result["status"] == "optimal"

    # Exactly one core
    assert result["allocation"]["core_a"] + result["allocation"]["core_b"] == 1

    # If core_a, then addon_1
    if result["allocation"]["core_a"] == 1:
        assert result["allocation"]["addon_1"] == 1

    # At least one addon
    assert result["allocation"]["addon_1"] + result["allocation"]["addon_2"] >= 1

    print("✓ Test passed\n")
    return result


if __name__ == "__main__":
    print("=" * 60)
    print("Running Optimization MCP Tests")
    print("=" * 60 + "\n")

    # Existing tests
    test_simple_allocation()
    test_infeasible_allocation()
    test_multi_resource_allocation()

    # Multi-objective tests
    test_multi_objective_two_functions()
    test_multi_objective_weight_distribution()
    test_multi_objective_validation()
    test_backward_compatibility()

    # Enhanced constraint tests
    test_conditional_constraints()
    test_disjunctive_constraints()
    test_mutex_constraints()
    test_combined_advanced_constraints()

    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)
