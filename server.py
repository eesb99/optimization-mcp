#!/usr/bin/env python3
"""
Optimization MCP Server

Model Context Protocol server providing optimization tools with Monte Carlo integration.

Tools:
- optimize_allocation: Resource allocation optimization
- optimize_robust: Robust optimization across Monte Carlo scenarios
"""

import sys
import json
import logging
from typing import Any, Dict
import asyncio

# Add src to path
sys.path.insert(0, str(__file__).replace('/server.py', '/src'))

from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# Import tool implementations
from src.api.allocation import optimize_allocation
from src.api.robust import optimize_robust
from src.api.portfolio import optimize_portfolio
from src.api.schedule import optimize_schedule
from src.api.execute import optimize_execute
from src.api.network_flow import optimize_network_flow
from src.api.pareto import optimize_pareto
from src.api.stochastic import optimize_stochastic

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('/tmp/optimization-mcp.log')]
)
logger = logging.getLogger('optimization-mcp')


# Create MCP server instance
app = Server("optimization-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    List available optimization tools.

    Returns:
        List of Tool objects with schemas
    """
    return [
        Tool(
            name="optimize_allocation",
            description=(
                "Optimize resource allocation across items to maximize/minimize objective. "
                "Supports Monte Carlo integration (percentile, expected, scenarios modes). "
                "Use cases: marketing budgets, production capacity, project selection, formulation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "objective": {
                        "type": "object",
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "number"}
                                    },
                                    "required": ["name", "value"]
                                }
                            },
                            "sense": {
                                "type": "string",
                                "enum": ["maximize", "minimize"]
                            }
                        },
                        "required": ["items", "sense"]
                    },
                    "resources": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "total": {"type": "number"}
                            },
                            "required": ["total"]
                        }
                    },
                    "item_requirements": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"}
                            },
                            "required": ["name"]
                        }
                    },
                    "constraints": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "items": {"type": "array", "items": {"type": "string"}},
                                "limit": {"type": "number"},
                                "type": {"type": "string", "enum": ["min", "max"]}
                            }
                        }
                    },
                    "monte_carlo_integration": {
                        "type": "object",
                        "properties": {
                            "mode": {
                                "type": "string",
                                "enum": ["percentile", "expected", "scenarios"]
                            },
                            "percentile": {"type": "string"},
                            "mc_output": {"type": "object"}
                        }
                    },
                    "solver_options": {
                        "type": "object",
                        "properties": {
                            "time_limit": {"type": "number"},
                            "verbose": {"type": "boolean"}
                        }
                    }
                },
                "required": ["objective", "resources", "item_requirements"]
            }
        ),
        Tool(
            name="optimize_robust",
            description=(
                "Find robust solutions that perform well across Monte Carlo scenarios. "
                "Optimizes for best average, worst case, or percentile performance. "
                "Use when you want allocation that works in 85%+ of scenarios."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "objective": {
                        "type": "object",
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"}
                                    },
                                    "required": ["name"]
                                }
                            },
                            "sense": {
                                "type": "string",
                                "enum": ["maximize", "minimize"]
                            }
                        },
                        "required": ["items", "sense"]
                    },
                    "resources": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "total": {"type": "number"}
                            },
                            "required": ["total"]
                        }
                    },
                    "item_requirements": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"}
                            },
                            "required": ["name"]
                        }
                    },
                    "monte_carlo_scenarios": {
                        "type": "object",
                        "properties": {
                            "scenarios": {"type": "array"}
                        },
                        "required": ["scenarios"]
                    },
                    "robustness_criterion": {
                        "type": "string",
                        "enum": ["best_average", "worst_case", "percentile"],
                        "default": "best_average"
                    },
                    "risk_tolerance": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "default": 0.85
                    },
                    "constraints": {
                        "type": "array",
                        "items": {"type": "object"}
                    },
                    "solver_options": {
                        "type": "object",
                        "properties": {
                            "time_limit": {"type": "number"},
                            "verbose": {"type": "boolean"}
                        }
                    }
                },
                "required": ["objective", "resources", "item_requirements", "monte_carlo_scenarios"]
            }
        ),
        Tool(
            name="optimize_portfolio",
            description=(
                "Portfolio optimization with Sharpe ratio, variance minimization, or return maximization. "
                "Handles quadratic risk metrics and asset correlations. "
                "Use cases: investment portfolio allocation, asset selection, risk-return optimization."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "assets": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "expected_return": {"type": "number"}
                            },
                            "required": ["name", "expected_return"]
                        }
                    },
                    "covariance_matrix": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "number"}
                        }
                    },
                    "constraints": {
                        "type": "object",
                        "properties": {
                            "max_weight": {"type": "number"},
                            "min_weight": {"type": "number"},
                            "target_return": {"type": "number"},
                            "target_risk": {"type": "number"},
                            "long_only": {"type": "boolean"}
                        }
                    },
                    "optimization_objective": {
                        "type": "string",
                        "enum": ["sharpe", "min_variance", "max_return"],
                        "default": "sharpe"
                    },
                    "risk_free_rate": {
                        "type": "number",
                        "default": 0.02
                    },
                    "monte_carlo_integration": {
                        "type": "object",
                        "properties": {
                            "mode": {
                                "type": "string",
                                "enum": ["percentile", "expected"]
                            },
                            "percentile": {"type": "string"},
                            "mc_output": {"type": "object"}
                        }
                    },
                    "solver_options": {
                        "type": "object",
                        "properties": {
                            "time_limit": {"type": "number"},
                            "verbose": {"type": "boolean"}
                        }
                    }
                },
                "required": ["assets", "covariance_matrix"]
            }
        ),
        Tool(
            name="optimize_schedule",
            description=(
                "Task scheduling with dependencies and resource constraints. "
                "Minimizes makespan or maximizes value. Handles precedence, deadlines, resource limits. "
                "Use cases: project scheduling, job shop scheduling, task prioritization."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "duration": {"type": "number"},
                                "value": {"type": "number"},
                                "dependencies": {"type": "array", "items": {"type": "string"}},
                                "resources": {"type": "object"}
                            },
                            "required": ["name", "duration"]
                        }
                    },
                    "resources": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {"total": {"type": "number"}},
                            "required": ["total"]
                        }
                    },
                    "time_horizon": {"type": "integer"},
                    "constraints": {"type": "array", "items": {"type": "object"}},
                    "optimization_objective": {
                        "type": "string",
                        "enum": ["minimize_makespan", "maximize_value"],
                        "default": "minimize_makespan"
                    },
                    "monte_carlo_integration": {"type": "object"},
                    "solver_options": {"type": "object"}
                },
                "required": ["tasks", "resources", "time_horizon"]
            }
        ),
        Tool(
            name="optimize_execute",
            description=(
                "Execute custom optimization with automatic solver selection and flexible problem specification. "
                "Supports PuLP (LP/MILP), SciPy (nonlinear), and CVXPY (quadratic). "
                "Use cases: rapid prototyping, custom formulations, power user optimization."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "problem_definition": {
                        "type": "object",
                        "properties": {
                            "variables": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "type": {"type": "string", "enum": ["continuous", "integer", "binary"]},
                                        "bounds": {"type": "array"}
                                    },
                                    "required": ["name", "type"]
                                }
                            },
                            "objective": {
                                "type": "object",
                                "properties": {
                                    "coefficients": {"type": "object"},
                                    "sense": {"type": "string", "enum": ["maximize", "minimize"]}
                                },
                                "required": ["coefficients", "sense"]
                            },
                            "constraints": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "coefficients": {"type": "object"},
                                        "type": {"type": "string"},
                                        "rhs": {"type": "number"}
                                    }
                                }
                            }
                        },
                        "required": ["variables", "objective"]
                    },
                    "auto_detect": {"type": "boolean", "default": true},
                    "solver_preference": {"type": "string", "enum": ["pulp", "scipy", "cvxpy"]},
                    "monte_carlo_integration": {"type": "object"},
                    "solver_options": {"type": "object"}
                },
                "required": ["problem_definition"]
            }
        ),
        Tool(
            name="optimize_network_flow",
            description=(
                "Optimize network flow problems: min-cost flow, max-flow, assignment. "
                "Uses specialized NetworkX algorithms (10-100x faster than general LP). "
                "Supports Monte Carlo integration for uncertain costs/demands. "
                "Use cases: supply chain routing, logistics, transportation, assignment problems."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "network": {
                        "type": "object",
                        "properties": {
                            "nodes": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "supply": {"type": "number"},
                                        "demand": {"type": "number"}
                                    },
                                    "required": ["id"]
                                }
                            },
                            "edges": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "from": {"type": "string"},
                                        "to": {"type": "string"},
                                        "capacity": {"type": "number"},
                                        "cost": {"type": "number"},
                                        "name": {"type": "string"}
                                    },
                                    "required": ["from", "to"]
                                }
                            }
                        },
                        "required": ["nodes", "edges"]
                    },
                    "flow_type": {
                        "type": "string",
                        "enum": ["min_cost", "max_flow", "assignment"],
                        "default": "min_cost"
                    },
                    "constraints": {"type": "array"},
                    "monte_carlo_integration": {"type": "object"},
                    "solver_options": {"type": "object"}
                },
                "required": ["network"]
            }
        ),
        Tool(
            name="optimize_pareto",
            description=(
                "Generate Pareto frontier for multi-objective optimization. "
                "Explores trade-offs between conflicting objectives (profit vs sustainability, cost vs quality). "
                "Returns non-dominated solutions spanning the entire trade-off space. "
                "Use cases: strategic planning, design optimization, multi-criteria decisions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "objectives": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "items": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "value": {"type": "number"}
                                        },
                                        "required": ["name", "value"]
                                    }
                                },
                                "sense": {"type": "string", "enum": ["maximize", "minimize"]}
                            },
                            "required": ["name", "items", "sense"]
                        },
                        "minItems": 2
                    },
                    "resources": {"type": "object"},
                    "item_requirements": {"type": "array"},
                    "constraints": {"type": "array"},
                    "num_points": {"type": "integer", "minimum": 2, "default": 20},
                    "monte_carlo_integration": {"type": "object"},
                    "solver_options": {"type": "object"}
                },
                "required": ["objectives", "resources", "item_requirements"]
            }
        ),
        Tool(
            name="optimize_stochastic",
            description=(
                "Two-stage stochastic programming with recourse decisions. "
                "Optimizes decisions over time under uncertainty: decide now, adapt later. "
                "Use cases: inventory management, capacity planning, portfolio rebalancing."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "first_stage": {"type": "object"},
                    "second_stage": {"type": "object"},
                    "scenarios": {"type": "array"},
                    "risk_measure": {"type": "string", "enum": ["expected", "cvar", "worst_case"], "default": "expected"},
                    "risk_parameter": {"type": "number", "default": 0.95},
                    "monte_carlo_integration": {"type": "object"},
                    "solver_options": {"type": "object"}
                },
                "required": ["first_stage", "second_stage", "scenarios"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    """
    Call an optimization tool.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        List of TextContent with results
    """
    logger.info(f"Tool called: {name}")
    logger.debug(f"Arguments: {json.dumps(arguments, indent=2)}")

    try:
        if name == "optimize_allocation":
            result = optimize_allocation(**arguments)
        elif name == "optimize_robust":
            result = optimize_robust(**arguments)
        elif name == "optimize_portfolio":
            result = optimize_portfolio(**arguments)
        elif name == "optimize_schedule":
            result = optimize_schedule(**arguments)
        elif name == "optimize_execute":
            result = optimize_execute(**arguments)
        elif name == "optimize_network_flow":
            result = optimize_network_flow(**arguments)
        elif name == "optimize_pareto":
            result = optimize_pareto(**arguments)
        elif name == "optimize_stochastic":
            result = optimize_stochastic(**arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

        logger.info(f"Tool {name} completed successfully")
        logger.debug(f"Result: {json.dumps(result, indent=2)}")

        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    except Exception as e:
        logger.error(f"Error in tool {name}: {str(e)}", exc_info=True)

        error_result = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "tool": name
        }

        return [TextContent(
            type="text",
            text=json.dumps(error_result, indent=2)
        )]


async def main():
    """Run the MCP server."""
    logger.info("Starting Optimization MCP Server")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {str(e)}", exc_info=True)
        sys.exit(1)
