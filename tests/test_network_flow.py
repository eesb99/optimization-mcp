"""
Test Network Flow Optimization

Tests for optimize_network_flow tool with NetworkX and PuLP solvers.
"""

import sys
sys.path.insert(0, '/Users/thianseongyee/.claude/mcp-servers/optimization-mcp')

from src.api.network_flow import optimize_network_flow


def test_simple_min_cost_flow():
    """Test basic 3-node min-cost flow network."""
    print("Test: Simple Min-Cost Flow")

    network = {
        "nodes": [
            {"id": "warehouse_A", "supply": 100},
            {"id": "customer_1", "demand": 40},
            {"id": "customer_2", "demand": 60}
        ],
        "edges": [
            {"from": "warehouse_A", "to": "customer_1", "capacity": 50, "cost": 5.0},
            {"from": "warehouse_A", "to": "customer_2", "capacity": 80, "cost": 3.0}
        ]
    }

    result = optimize_network_flow(network, flow_type="min_cost")

    print(f"  Status: {result['status']}")
    print(f"  Solver: {result['solver']}")
    print(f"  Total cost: {result.get('total_cost')}")
    print(f"  Flow solution: {result.get('flow_solution')}")

    # Assertions
    assert result["status"] == "optimal"
    assert result["is_optimal"] == True
    assert "flow_solution" in result
    assert "total_cost" in result

    # Verify flow values
    flow_sol = result["flow_solution"]
    assert abs(flow_sol["flow_warehouse_A_customer_1"] - 40) < 0.01
    assert abs(flow_sol["flow_warehouse_A_customer_2"] - 60) < 0.01

    # Verify cost (40*5 + 60*3 = 200 + 180 = 380)
    assert abs(result["total_cost"] - 380.0) < 0.01

    print("✓ Test passed\n")
    return result


def test_max_flow_single_source_sink():
    """Test max-flow problem with bottleneck edges."""
    print("Test: Max Flow with Bottleneck")

    network = {
        "nodes": [
            {"id": "source", "supply": 1000},  # Large supply
            {"id": "intermediate", "demand": 0},
            {"id": "sink", "demand": 1000}  # Large demand
        ],
        "edges": [
            {"from": "source", "to": "intermediate", "capacity": 50},  # Bottleneck
            {"from": "intermediate", "to": "sink", "capacity": 100}
        ]
    }

    result = optimize_network_flow(network, flow_type="max_flow")

    print(f"  Status: {result['status']}")
    print(f"  Solver: {result['solver']}")
    print(f"  Total flow: {result.get('total_flow')}")
    print(f"  Bottlenecks: {len(result.get('bottlenecks', []))}")

    # Assertions
    assert result["status"] == "optimal"
    assert "total_flow" in result

    # Max flow should be limited by bottleneck (capacity 50)
    assert abs(result["total_flow"] - 50.0) < 0.01

    # Check bottleneck identification
    bottlenecks = result.get("bottlenecks", [])
    assert len(bottlenecks) > 0
    assert bottlenecks[0]["utilization"] >= 0.99

    print("✓ Test passed\n")
    return result


def test_assignment_problem():
    """Test assignment problem (bipartite matching)."""
    print("Test: Assignment Problem")

    network = {
        "nodes": [
            {"id": "worker_1", "supply": 1},
            {"id": "worker_2", "supply": 1},
            {"id": "task_A", "demand": 1},
            {"id": "task_B", "demand": 1}
        ],
        "edges": [
            {"from": "worker_1", "to": "task_A", "cost": 10},
            {"from": "worker_1", "to": "task_B", "cost": 15},
            {"from": "worker_2", "to": "task_A", "cost": 12},
            {"from": "worker_2", "to": "task_B", "cost": 8}
        ]
    }

    result = optimize_network_flow(network, flow_type="assignment")

    print(f"  Status: {result['status']}")
    print(f"  Solver: {result['solver']}")
    print(f"  Total cost: {result.get('total_cost')}")
    print(f"  Assignments: {result.get('flow_solution')}")

    # Assertions
    assert result["status"] == "optimal"
    assert "total_cost" in result

    # Optimal assignment: worker_1→task_A (10) + worker_2→task_B (8) = 18
    assert abs(result["total_cost"] - 18.0) < 0.01

    # Verify one-to-one matching
    flow_sol = result["flow_solution"]
    assignments = {k: v for k, v in flow_sol.items() if v > 0.5}
    assert len(assignments) == 2  # Two assignments

    print("✓ Test passed\n")
    return result


def test_moderate_scale_network():
    """Test moderate network for performance (10 nodes, deterministic)."""
    print("Test: Moderate Scale Network (10 nodes, 15 edges)")

    # Create deterministic 10-node network
    nodes = [
        {"id": "S1", "supply": 50},
        {"id": "S2", "supply": 50},
    ]
    for i in range(5):
        nodes.append({"id": f"D{i}", "demand": 20})

    # Create edges in a reasonable pattern
    edges = []
    for s in ["S1", "S2"]:
        for i in range(5):
            edges.append({
                "from": s,
                "to": f"D{i}",
                "capacity": 30,
                "cost": (i + 1) * 2.0
            })

    network = {"nodes": nodes, "edges": edges}

    result = optimize_network_flow(network, flow_type="min_cost")

    print(f"  Status: {result['status']}")
    print(f"  Solver: {result['solver']}")
    print(f"  Solve time: {result['solve_time_seconds']:.3f}s")

    # Assertions
    assert "status" in result
    assert result["solve_time_seconds"] < 2.0  # Should be fast

    if result["status"] == "optimal":
        print(f"  Total cost: {result.get('total_cost')}")
        assert "total_cost" in result

    print("✓ Test passed (performance check)\n")
    return result


def test_infeasible_network():
    """Test infeasible network (supply != demand) caught by validation."""
    print("Test: Infeasible Network (Validation)")

    network = {
        "nodes": [
            {"id": "source", "supply": 100},
            {"id": "sink", "demand": 50}  # Imbalance!
        ],
        "edges": [
            {"from": "source", "to": "sink", "capacity": 100, "cost": 1.0}
        ]
    }

    # Should raise ValueError during validation
    try:
        result = optimize_network_flow(network, flow_type="min_cost")
        # If we get here, validation didn't catch it (unexpected)
        assert False, "Expected ValueError for supply/demand imbalance"
    except ValueError as e:
        # Expected - validation caught the imbalance
        assert "Flow conservation violated" in str(e)
        print(f"  Validation error (expected): {str(e)[:80]}...")
        print("✓ Test passed (validation caught infeasibility)\n")
        return None


def test_networkx_vs_pulp_comparison():
    """Test NetworkX vs PuLP solver comparison."""
    print("Test: NetworkX vs PuLP Comparison")

    network = {
        "nodes": [
            {"id": "A", "supply": 50},
            {"id": "B", "demand": 20},
            {"id": "C", "demand": 30}
        ],
        "edges": [
            {"from": "A", "to": "B", "capacity": 25, "cost": 2.0},
            {"from": "A", "to": "C", "capacity": 35, "cost": 3.0}
        ]
    }

    # Solve with NetworkX (default)
    result_nx = optimize_network_flow(
        network,
        flow_type="min_cost",
        solver_options={"solver": "networkx", "verbose": False}
    )

    # Solve with PuLP (fallback)
    result_pulp = optimize_network_flow(
        network,
        flow_type="min_cost",
        solver_options={"solver": "pulp", "verbose": False}
    )

    print(f"  NetworkX - Status: {result_nx['status']}, Cost: {result_nx.get('total_cost')}")
    print(f"  PuLP - Status: {result_pulp['status']}, Cost: {result_pulp.get('total_cost')}")

    # Assertions
    assert result_nx["solver"] == "networkx"
    assert result_pulp["solver"] == "pulp"

    # Both should find optimal solution
    assert result_nx["status"] == "optimal"
    assert result_pulp["status"] == "optimal"

    # Objectives should match (within tolerance)
    assert abs(result_nx["total_cost"] - result_pulp["total_cost"]) < 0.01

    # NetworkX should be faster (for pure network flow)
    print(f"  NetworkX time: {result_nx['solve_time_seconds']:.4f}s")
    print(f"  PuLP time: {result_pulp['solve_time_seconds']:.4f}s")

    print("✓ Test passed (solvers agree)\n")
    return result_nx, result_pulp


def test_node_balance_and_bottlenecks():
    """Test node balance calculation and bottleneck detection."""
    print("Test: Node Balance and Bottleneck Analysis")

    network = {
        "nodes": [
            {"id": "factory", "supply": 100},
            {"id": "warehouse", "demand": 0},
            {"id": "store_1", "demand": 40},
            {"id": "store_2", "demand": 60}
        ],
        "edges": [
            {"from": "factory", "to": "warehouse", "capacity": 100, "cost": 1.0},
            {"from": "warehouse", "to": "store_1", "capacity": 40, "cost": 2.0},
            {"from": "warehouse", "to": "store_2", "capacity": 70, "cost": 2.5}
        ]
    }

    result = optimize_network_flow(network, flow_type="min_cost")

    print(f"  Status: {result['status']}")

    # Check node balance
    node_balance = result.get("node_balance", {})
    print(f"  Node balance: {node_balance}")

    assert "node_balance" in result
    assert "warehouse" in node_balance

    # Warehouse should have balanced flow (inflow = outflow)
    warehouse_balance = node_balance["warehouse"]
    assert abs(warehouse_balance["inflow"] - warehouse_balance["outflow"]) < 0.01

    # Check bottlenecks
    bottlenecks = result.get("bottlenecks", [])
    print(f"  Bottlenecks: {len(bottlenecks)}")

    if bottlenecks:
        print(f"    {bottlenecks[0]}")
        assert all(b["utilization"] >= 0.99 for b in bottlenecks)

    print("✓ Test passed\n")
    return result


def test_mc_compatible_output():
    """Test Monte Carlo compatible output generation."""
    print("Test: Monte Carlo Compatible Output")

    network = {
        "nodes": [
            {"id": "A", "supply": 50},
            {"id": "B", "demand": 50}
        ],
        "edges": [
            {"from": "A", "to": "B", "capacity": 100, "cost": 5.0}
        ]
    }

    result = optimize_network_flow(network, flow_type="min_cost")

    print(f"  Status: {result['status']}")

    # Check MC compatible output
    assert "monte_carlo_compatible" in result
    mc_output = result["monte_carlo_compatible"]

    assert "decision_variables" in mc_output
    assert "assumptions" in mc_output
    assert "outcome_function" in mc_output
    assert "recommended_next_tool" in mc_output

    print(f"  MC output keys: {list(mc_output.keys())}")
    print(f"  Recommended next: {mc_output['recommended_next_tool']}")

    print("✓ Test passed\n")
    return result


# Main test runner
if __name__ == "__main__":
    print("=" * 60)
    print("Running Network Flow Optimization Tests")
    print("=" * 60 + "\n")

    test_simple_min_cost_flow()
    test_max_flow_single_source_sink()
    test_assignment_problem()
    test_moderate_scale_network()
    test_infeasible_network()
    test_networkx_vs_pulp_comparison()
    test_node_balance_and_bottlenecks()
    test_mc_compatible_output()

    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)
