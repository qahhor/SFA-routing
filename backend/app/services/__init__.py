"""
Services module.

Provides business logic for route optimization:
- OSRM client for distance matrices
- VROOM solver for VRP
- OR-Tools solver for complex routing
- Greedy solver as fallback
- Weekly planner for SFA
- Route optimizer for delivery
- PDF export
"""
from app.services.osrm_client import OSRMClient, osrm_client
from app.services.vroom_solver import VROOMSolver, vroom_solver
from app.services.weekly_planner import WeeklyPlanner
from app.services.route_optimizer import RouteOptimizer, route_optimizer
from app.services.pdf_export import PDFExporter, pdf_exporter

# Import solver interface and implementations
from app.services.solver_interface import (
    RouteSolver,
    SolverFactory,
    SolverType,
    RoutingProblem,
    SolutionResult,
    Route,
    RouteStep,
    Location,
    VehicleConfig,
    Job,
    # FMCG-specific
    ClientCategory,
    VisitPurpose,
    RegionalConfig,
    RegionalConstraints,
)

# Import and register solver implementations
# These must be imported to trigger the @SolverFactory.register decorators
from app.services.greedy_solver import GreedySolver

# OR-Tools is optional
try:
    from app.services.ortools_solver import ORToolsSolver
except ImportError:
    ORToolsSolver = None  # type: ignore

__all__ = [
    # Clients
    "OSRMClient",
    "osrm_client",
    "VROOMSolver",
    "vroom_solver",
    # Services
    "WeeklyPlanner",
    "RouteOptimizer",
    "route_optimizer",
    "PDFExporter",
    "pdf_exporter",
    # Solver interface
    "RouteSolver",
    "SolverFactory",
    "SolverType",
    "RoutingProblem",
    "SolutionResult",
    "Route",
    "RouteStep",
    "Location",
    "VehicleConfig",
    "Job",
    # FMCG-specific
    "ClientCategory",
    "VisitPurpose",
    "RegionalConfig",
    "RegionalConstraints",
    # Solver implementations
    "GreedySolver",
    "ORToolsSolver",
]
