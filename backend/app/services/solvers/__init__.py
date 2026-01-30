"""
Routing solvers sub-package.

Contains all VRP/TSP solving algorithms:
- VROOM solver (fast, external service)
- OR-Tools solver (complex constraints)
- Genetic Algorithm solver (large-scale problems)
- Greedy solver (fallback)
- Smart solver selector
"""
from app.services.solvers.solver_interface import (
    RouteSolver,
    SolverFactory,
    SolverType,
    RoutingProblem,
    Job,
    VehicleConfig,
    Location,
    SolutionResult,
    Route,
    RouteStep,
    TransportMode,
    Break,
    # FMCG-specific
    ClientCategory,
    VisitPurpose,
    RegionalConfig,
    RegionalConstraints,
)
from app.services.solvers.solver_selector import (
    SmartSolverSelector,
    ProblemFeatures,
    solver_selector,
)
from app.services.solvers.vroom_solver import VROOMSolver, vroom_solver
from app.services.solvers.ortools_solver import ORToolsSolver
from app.services.solvers.genetic_solver import GeneticSolver, GAConfig
from app.services.solvers.greedy_solver import GreedySolver

__all__ = [
    # Base classes
    "RouteSolver",
    "SolverFactory",
    "SolverType",
    "RoutingProblem",
    "Job",
    "VehicleConfig",
    "Location",
    "SolutionResult",
    "Route",
    "RouteStep",
    "TransportMode",
    "Break",
    # FMCG-specific
    "ClientCategory",
    "VisitPurpose",
    "RegionalConfig",
    "RegionalConstraints",
    # Selector
    "SmartSolverSelector",
    "ProblemFeatures",
    "solver_selector",
    # Solvers
    "VROOMSolver",
    "vroom_solver",
    "ORToolsSolver",
    "GeneticSolver",
    "GAConfig",
    "GreedySolver",
]
