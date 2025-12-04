# Optimization MCP - Project Documentation

**Project**: Optimization MCP Server for Claude Code
**Purpose**: Constraint-based optimization with Monte Carlo integration
**Status**: Production Ready (v2.2.0 - Phase 1 Network Flow Complete)
**Last Updated**: 2025-12-04

---

## Project Overview

### Vision
Provide comprehensive optimization capabilities that integrate seamlessly with Monte Carlo analysis, enabling data-driven decisions under uncertainty.

### Core Principles
1. **Zero-friction workflows** - Optimization outputs feed directly into MC validation
2. **Production-ready solvers** - Open-source, battle-tested backends
3. **Deep MC integration** - Every tool Monte Carlo aware
4. **Extensible architecture** - Clean abstractions for future tools

---

## Key Decisions

### Decision 1: Solver Selection Strategy
**Date**: 2025-12-01
**Context**: Need multiple solver backends for different problem types

**Options Considered**:
1. Single solver (Gurobi or CPLEX) - requires expensive commercial license
2. PuLP only - can't handle nonlinear or quadratic
3. Multiple open-source solvers - more complexity but comprehensive

**Decision**: Multi-solver architecture with PuLP, SciPy, CVXPY

**Rationale**:
- PuLP (CBC): Excellent for discrete/integer problems, handles 10K+ variables
- SciPy: Native nonlinear support, good for smooth continuous problems
- CVXPY: Quadratic programming for portfolio optimization
- All open-source, no licensing costs
- BaseSolver abstraction makes adding solvers easy

**Outcome**: ✅ Successfully implemented, each solver handles its strengths

---

### Decision 2: Multi-Objective via Weighted Scalarization
**Date**: 2025-12-02
**Context**: User needs multi-criteria optimization (profit vs sustainability)

**Options Considered**:
1. Weighted scalarization - combine objectives with weights
2. Pareto optimization - find all non-dominated solutions
3. Lexicographic - optimize objectives in priority order

**Decision**: Weighted scalarization for v2.0.0, Pareto deferred to future

**Rationale**:
- Weighted scalarization is simple and fast
- Integrates seamlessly with existing solver infrastructure
- User provides weights → clear decision
- Pareto requires multiple solves and visualization (complex)
- 80/20 rule: weighted covers 80% of use cases

**Outcome**: ✅ Implemented with backward compatibility, 100% test pass rate

---

### Decision 3: CVXPY Solver Backend Selection
**Date**: 2025-12-02
**Context**: CVXPY supports multiple backends (ECOS, SCS, OSQP, CLARABEL, etc.)

**Options Tested**:
1. ECOS - Not bundled with CVXPY, installation issues
2. OSQP - Bundled, fast for QP, but can't handle some quadratic constraints
3. SCS - Bundled, general convex solver (QP/SOCP/SDP)
4. CLARABEL - Bundled, robust for LP

**Decision**: SCS as default for all continuous problems

**Rationale**:
- SCS handles all convex problem types (LP, QP, SOCP, SDP)
- Bundled with CVXPY (no extra installation)
- Successfully solved all test cases (LP, QP, quadratic constraints)
- More robust than OSQP for general problems
- Slightly slower but more reliable

**Outcome**: ✅ All 6 CVXPY tests + 6 portfolio tests passing

---

### Decision 4: Scheduling Formulation (Time-Indexed Variables)
**Date**: 2025-12-02
**Context**: Multiple ways to formulate scheduling problems

**Options Considered**:
1. Time-indexed: x[task,time] binary variables
2. Continuous start times: s_i continuous + precedence constraints
3. Disjunctive: Big-M method for non-overlapping

**Decision**: Time-indexed formulation (option 1)

**Rationale**:
- Exact representation of task timing
- Easy to add resource constraints at each time period
- Simple precedence constraints
- Easier critical path detection
- Downside: O(n*T) variables but acceptable for <50 tasks

**Trade-offs**:
- ➕ Straightforward implementation
- ➕ Easy to add deadlines, release times
- ➕ Resource constraints natural
- ➖ More variables than continuous formulation
- ➖ May be slow for 100+ tasks or 100+ time horizon

**Outcome**: ✅ Working well for typical project scheduling (6/6 tests passing)

---

### Decision 5: Enhanced Constraints via PuLP Reformulation
**Date**: 2025-12-02
**Context**: Need conditional, OR, XOR logic for complex business rules

**Options Considered**:
1. Reformulate as linear constraints (x_b >= x_a for if-then)
2. Add special solver support (requires custom backend)
3. Use constraint programming (different paradigm)

**Decision**: Linear reformulation (option 1)

**Rationale**:
- Works with existing PuLP solver
- Standard MIP techniques:
  - Conditional: x_then >= x_condition
  - Disjunctive: sum(x_i) >= N
  - Mutex: sum(x_i) = N
- No new dependencies
- Efficient for typical problem sizes

**Outcome**: ✅ All constraint types working (11/11 tests)

---

### Decision 6: NetworkX for Pure Network Flow (v2.2.0 Phase 1)
**Date**: 2025-12-04
**Context**: Need 10-100x speedup for logistics/routing problems at 1K-10K variable scale

**Options Considered**:
1. Keep PuLP general LP for all problems - simple but slow
2. Add NetworkX specialized algorithms - faster but needs new solver backend
3. Use commercial solver (Gurobi Network) - fast but expensive license

**Decision**: NetworkX specialized solver with PuLP fallback (option 2)

**Rationale**:
- NetworkX algorithms exploit network structure (10-100x faster)
- Pure Python, no C dependencies, easy install
- Network simplex for min-cost flow: O(V²E) vs general LP
- Edmonds-Karp for max flow: O(VE²) specialized algorithm
- PuLP fallback handles multi-commodity and side constraints
- User problems span 1K-10K variables where speedup is critical

**Implementation**:
- NetworkXSolver class (350 LOC) inheriting from BaseSolver
- optimize_network_flow tool (656 LOC)
- Explicit edge info passing (from/to nodes) to avoid variable name parsing
- Node attributes for demand (not dict parameter - API bug fixed)
- 8 comprehensive tests

**Trade-offs**:
- ➕ 10-100x speedup on pure network flow (0.0001s vs 0.5s for small networks)
- ➕ Scales to 10K nodes efficiently
- ➕ Bottleneck analysis built-in
- ➖ Additional dependency (networkx>=3.0, but small 300KB)
- ➖ Limited to pure network flow (multi-commodity needs PuLP)

**Outcome**: ✅ 42/42 tests passing, NetworkX 1000x faster than PuLP on test cases

---

## Technical Findings

### Finding 1: CVXPY Problem Classification
**Date**: 2025-12-02

**Discovery**: CVXPY auto-classifies problems as DCP (Disciplined Convex Programming)

**Details**:
- If problem is DCP → can solve with convex solvers
- If not DCP → error before solving (helpful!)
- Portfolio problems are DCP (quadratic form is convex)
- Prevents wasting time on unsolvable non-convex problems

**Implication**: CVXPY's DCP analysis provides free problem validation

---

### Finding 2: Shadow Prices Only for LP
**Date**: 2025-12-01

**Discovery**: PuLP provides shadow prices (dual values) only for LP problems, not MIP

**Details**:
- If problem has integer/binary variables → no shadow prices
- `constraint.pi` returns None for MIP
- SciPy also doesn't provide duals for constrained problems

**Implication**:
- Shadow price analysis only for continuous relaxation
- For MIP, use sensitivity analysis instead

**Workaround**: Document limitation, suggest continuous approximation for sensitivity

---

### Finding 3: Critical Path Detection Algorithm
**Date**: 2025-12-02

**Discovery**: Critical path can be identified by backward tracing from makespan

**Algorithm**:
```python
1. Find task with latest end time (determines makespan)
2. Trace backward through dependencies
3. At each step, find predecessor that finishes latest
4. Continue until reaching task with no dependencies
```

**Result**: O(n²) in worst case, but works well for typical project graphs

---

### Finding 4: Resource Timeline Complexity
**Date**: 2025-12-02

**Discovery**: Resource usage calculation is O(T × n) where T=time_horizon, n=tasks

**Details**:
- For each time t, must check all tasks to see if active
- Creates detailed timeline showing utilization over time
- Useful for visualizing resource bottlenecks

**Performance**:
- Fast for T<100, n<50 (typical projects)
- May need optimization for very large problems

---

## Lessons Learned

### Lesson 1: Phase-by-Phase Testing Essential
**Context**: Implemented 5 phases with gate checkpoints

**Learning**: Testing after each phase caught bugs early and prevented compounding errors

**Evidence**:
- Phase 1: Caught KeyError in multi-objective handling
- Phase 2: Identified solver backend issues immediately
- Phase 3: Portfolio tests revealed SCS robustness
- Phase 4: Objective ordering bug found quickly
- Phase 5: Constraint tests validated all logic paths

**Application**: Always use gate checkpoints for multi-phase projects

---

### Lesson 2: Solver Abstraction Pays Off
**Context**: BaseSolver abstract class with PuLP, SciPy, CVXPY implementations

**Learning**: Clean abstraction made adding CVXPY trivial (~400 LOC, 6h)

**Evidence**:
- All solvers implement same interface
- Tools can switch solvers without changes
- New solvers follow same pattern
- Test suite reusable across solvers

**Application**: Invest in abstractions early for extensibility

---

### Lesson 3: Validation First Saves Debugging Time
**Context**: Comprehensive DataConverter validation before solving

**Learning**: Early validation with helpful errors prevents cryptic solver failures

**Evidence**:
- Weight sum validation catches user errors immediately
- Covariance matrix dimension check prevents silent bugs
- Missing key errors show exactly what's wrong
- 0 solver failures due to bad inputs in testing

**Application**: Validate inputs thoroughly before expensive operations

---

### Lesson 4: Documentation with Examples Crucial
**Context**: Every tool has multiple examples in README

**Learning**: Examples make tools accessible and show best practices

**Evidence**:
- README examples directly usable as test cases
- Users can copy-paste and modify
- Shows integration with MC tools
- Demonstrates all parameters

**Application**: Write examples before implementation (TDD for docs)

---

## Architecture Decisions

### Pattern 1: Tool Structure
**Rationale**: Consistent pattern across all tools

```
Tool Function (public API)
├─ Input Validation (DataConverter)
├─ MC Integration (optional)
├─ Solver Setup (create vars, objective, constraints)
├─ Solving
├─ Result Building
└─ MC Output Formatting
```

**Benefits**:
- Predictable code organization
- Easy to add new tools following pattern
- Testable components

---

### Pattern 2: Monte Carlo Integration Points
**Rationale**: Three integration modes for flexibility

1. **Percentile Mode**: Use P10/P50/P90 values
   - Conservative (P10), Base case (P50), Optimistic (P90)

2. **Expected Mode**: Use mean values
   - Best for risk-neutral decisions

3. **Scenarios Mode**: Evaluate across all scenarios
   - Used by optimize_robust for robustness testing

**Benefits**: Covers all use cases from simple to sophisticated

---

### Pattern 3: Result Standardization
**Rationale**: Consistent output structure enables tool chaining

**Standard Fields**:
- `status`: "optimal", "infeasible", "unbounded", "error"
- `is_optimal`: Boolean
- `is_feasible`: Boolean
- `solve_time_seconds`: Float
- Tool-specific results (allocation, weights, schedule)
- `monte_carlo_compatible`: MC validation output

**Benefits**: Predictable API, easy integration, works with all downstream tools

---

## Future Roadmap

### Week 3 ✅ COMPLETE (2025-12-02)
**Goal**: Custom workflows and orchestration
**Status**: ✅ Delivered

**Phase 6: Execute Tool** (~450 LOC, 8-10h) ✅
- ✅ Problem type auto-detection
- ✅ Automatic solver selection (PuLP/SciPy/CVXPY)
- ✅ Flexible problem specification (dict-based)
- ✅ 5/5 tests passing

**Phase 7: Orchestration Skill** (~250 LOC, 4-6h) ✅
- ✅ End-to-end robust optimization workflow (7 phases)
- ✅ Multi-tool chaining (optimization + Monte Carlo)
- ✅ Comprehensive decision reporting
- ✅ Memory integration

**Delivered**: v2.1.0 (5 tools + 1 skill, 34/34 tests passing)

---

### Week 4+ (Future)
**Long-term Enhancements**:

1. **Pareto Optimization** (~600 LOC)
   - Multi-objective with Pareto frontier
   - Generate multiple non-dominated solutions
   - Visualization support

2. **Stochastic Programming** (~700 LOC)
   - Multi-stage decisions under uncertainty
   - Scenario tree formulation
   - Recourse variables

3. **Network Flow Optimization** (~500 LOC)
   - Min-cost flow, max-flow
   - Transportation problems
   - Assignment problems

4. **Combinatorial Optimization** (~600 LOC)
   - Traveling salesman problem (TSP)
   - Vehicle routing problem (VRP)
   - Knapsack variants

5. **Column Generation** (~800 LOC)
   - Large-scale scheduling (100+ tasks)
   - Cutting stock problems
   - Crew scheduling

**Target**: v3.0.0 with 8-10 tools total

---

## Integration Points

### With Monte Carlo MCP
**Workflow**: Optimize → Validate → Test Robustness

```python
# Step 1: Optimize with MC values
result = optimize_allocation(
    monte_carlo_integration={
        "mode": "percentile",
        "percentile": "p50",
        "mc_output": mc_simulation_result
    }
)

# Step 2: Validate confidence
confidence = validate_reasoning_confidence(
    **result["monte_carlo_compatible"]["recommended_params"]
)

# Step 3: Test robustness
robustness = test_assumption_robustness(
    base_answer=result["allocation"],
    **result["monte_carlo_compatible"]["assumptions"]
)
```

**Status**: ✅ Working end-to-end

---

### With Business Strategy Agents
**Agents Using Optimization MCP**:
- business-advisor (resource allocation)
- cfo (budget optimization)
- portfolio-risk-manager (portfolio allocation)
- sme-business-strategist (constrained planning)

**Integration**: Agents invoke optimize_* tools via MCP interface

---

## References

### Code Patterns
- **BaseSolver**: `src/solvers/base_solver.py:30-269`
- **Tool Template**: `src/api/allocation.py:22-165`
- **MC Integration**: `src/integration/monte_carlo.py`
- **Validation**: `src/integration/data_converters.py:14-165`

### External Documentation
- PuLP: https://coin-or.github.io/pulp/
- SciPy optimize: https://docs.scipy.org/doc/scipy/reference/optimize.html
- CVXPY: https://www.cvxpy.org/
- CBC solver: https://github.com/coin-or/Cbc

### Memory Entries
- `/recall optimization-mcp-v2-complete` - Completion summary
- `/recall optimization-solver-algorithms` - Algorithm details
- `/recall optimization-constraint-types` - Constraint reference
- `/recall optimization-workflows` - Canonical workflows
- `/recall optimization-best-practices` - Usage guidelines

---

## Success Metrics

### Quality Metrics
- ✅ Test Coverage: 29 comprehensive tests
- ✅ Pass Rate: 100% (29/29)
- ✅ Documentation: Examples for all features
- ✅ Error Handling: Helpful validation messages
- ✅ Backward Compatibility: Week 1 API unchanged

### Performance Metrics
- ✅ Small problems (<50 vars): <1s
- ✅ Medium problems (50-500 vars): <10s
- ✅ Portfolio (10-100 assets): <5s
- ✅ Scheduling (<20 tasks): <10s

### Feature Completeness
- ✅ Multi-objective: Weighted scalarization
- ✅ Quadratic programming: Portfolio variance
- ✅ Scheduling: Dependencies + critical path
- ✅ Enhanced constraints: If-then, OR, XOR
- ⏸️ Pareto optimization: Deferred to v3.0
- ⏸️ Stochastic programming: Deferred to v3.0

---

## Risk Assessment

### Current Risks

**Risk 1: Performance with Large Problems**
- **Probability**: Medium
- **Impact**: Medium
- **Mitigation**: Document scale limits, suggest decomposition
- **Status**: Acceptable for target use cases

**Risk 2: Covariance Matrix Quality**
- **Probability**: Medium
- **Impact**: Medium
- **Mitigation**: Validate matrix properties (PSD), provide estimation guidance
- **Status**: User responsibility, documented

**Risk 3: Scheduling Scalability**
- **Probability**: Low
- **Impact**: Medium
- **Mitigation**: Time-indexed works for <50 tasks, column generation for larger
- **Status**: Monitored, future enhancement planned

### Mitigated Risks

**Risk 4: Solver Installation** - ✅ Resolved
- Used bundled solvers (SCS, OSQP, CLARABEL)
- No extra installation steps

**Risk 5: Backward Compatibility** - ✅ Resolved
- Comprehensive regression testing
- Separate validation for single vs multi-objective

---

## Best Practices Discovered

### Practice 1: Start Simple, Test Often
**Discovery**: Phase-by-phase with gate checkpoints prevented regressions

**Implementation**:
- Each phase: implement → test → gate → proceed
- No Phase N+1 work until Phase N tests pass
- Caught 5 bugs immediately at gates

**Result**: 100% test pass rate, no regression bugs

---

### Practice 2: Use Percentile Modes for Risk Management
**Discovery**: P10/P50/P90 provide clear risk spectrum

**Application**:
- P10 (pessimistic): Conservative planning
- P50 (base case): Expected outcome
- P90 (optimistic): Stretch goals

**Example**:
```python
# Conservative allocation (P10)
conservative = optimize_allocation(
    monte_carlo_integration={"mode": "percentile", "percentile": "p10", ...}
)

# Base case (P50)
base = optimize_allocation(
    monte_carlo_integration={"mode": "percentile", "percentile": "p50", ...}
)

# Compare strategies across scenarios
```

---

### Practice 3: Check Shadow Prices for Bottleneck Identification
**Discovery**: Shadow prices show marginal value of resources

**Application**:
```python
result = optimize_allocation(...)
shadow_prices = result["shadow_prices"]
# {"budget": 1.25, "time": 0.0}
# → Extra $1 budget worth $1.25 value
# → Extra 1 hour time worth $0 (time not a bottleneck)
```

**Value**: Guides where to invest for maximum ROI

---

## Technical Debt

### Minor Technical Debt

**Item 1**: Time-indexed scheduling may be slow for large problems
- **Impact**: Low (target use case is <50 tasks)
- **Solution**: Implement column generation if needed
- **Priority**: Low

**Item 2**: Multi-objective only supports weighted scalarization
- **Impact**: Medium (some users may want Pareto frontier)
- **Solution**: Add Pareto optimization in v3.0
- **Priority**: Medium

**Item 3**: Portfolio requires user-provided covariance matrix
- **Impact**: Low (financial users have this)
- **Solution**: Add covariance estimation helper
- **Priority**: Low

### No Major Technical Debt
- All code follows established patterns
- Comprehensive test coverage
- Proper error handling
- Clean abstractions

---

## Appendix

### Problem Type → Solver Mapping

| Problem Type | Solver | Algorithm | When to Use |
|--------------|--------|-----------|-------------|
| Linear discrete | PuLP | CBC branch-and-cut | Resource allocation, selection |
| Linear continuous | PuLP or CVXPY | Simplex/Interior point | Blending, production planning |
| Quadratic | CVXPY | SCS/OSQP | Portfolio, least squares |
| Nonlinear smooth | SciPy | L-BFGS-B, SLSQP | Continuous optimization |
| Mixed-integer | PuLP | CBC branch-and-cut | Scheduling, assignment |

### Constraint Type → Formulation

| Constraint Type | Mathematical Form | MILP Formulation |
|----------------|-------------------|------------------|
| Linear min/max | sum(x_i) ≤ or ≥ b | Direct |
| Conditional | if x_a then x_b | x_b ≥ x_a |
| Disjunctive | at least N of M | sum(x_i) ≥ N |
| Mutex | exactly N of M | sum(x_i) = N |
| Quadratic | x'Qx ≤ b | CVXPY quad_form |

### File Size Reference

| File | LOC | Purpose |
|------|-----|---------|
| allocation.py | 560 | Multi-obj + constraints |
| portfolio.py | 445 | Portfolio optimization |
| schedule.py | 555 | Task scheduling |
| robust.py | 509 | Robust optimization |
| cvxpy_solver.py | 397 | Quadratic programming |
| pulp_solver.py | 391 | LP/MILP solver |
| scipy_solver.py | 403 | Nonlinear solver |
| data_converters.py | 510 | Validation utilities |
| monte_carlo.py | 417 | MC integration |

**Total Core**: ~4,200 LOC
**Total Tests**: ~1,416 LOC
**Total Docs**: ~500 LOC

---

*This document captures key decisions, findings, and lessons from v1.0.0 → v2.0.0 development.*
