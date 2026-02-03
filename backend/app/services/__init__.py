"""
Services module.

Provides business logic for route optimization:
- Solvers: VROOM, OR-Tools, Genetic, Greedy, SmartSelector
- Routing: OSRM client, route optimizer, clustering
- Planning: Weekly planner, rerouting, predictive rerouting
- Caching: Cache warmer, parallel matrix computation
- Realtime: Event pipeline, WebSocket, spatial index
- Security: Encryption, anonymization, GDPR compliance
- Analytics: Service time, skill matching, ETA calibration
"""

# Analytics (many classes, import selectively)
from app.services.analytics import (
    AgentSkills,
    ClientSatisfactionInputs,
    ClientVisitFeatures,
    CustomerSatisfactionScore,
    ETACalibrationData,
    ETACalibrationService,
    PredictiveVisitFrequency,
    ServiceTimeCalculator,
    SkillBasedAssignment,
    SmartPriorityRefresh,
    TrafficAwareETA,
    TrafficProfile,
    VisitFeedback,
    VisitFeedbackProcessor,
    VisitOutcome,
)

# ============================================================
# Caching sub-package
# ============================================================
from app.services.caching import (
    CachedParallelMatrixComputer,
    CacheWarmer,
    MatrixCache,
    ParallelMatrixComputer,
    WarmingStrategy,
)

# ============================================================
# Root-level services
# ============================================================
from app.services.pdf_export import PDFExporter, pdf_exporter

# ============================================================
# Planning sub-package
# ============================================================
from app.services.planning import (
    PredictiveReroutingEngine,
    RerouteResult,
    ReroutingService,
    ScheduleFeasibilityCheck,
    WeeklyPlanner,
    predictive_engine,
    rerouting_service,
    weekly_planner,
)

# ============================================================
# Realtime sub-package
# ============================================================
from app.services.realtime import (  # Event pipeline; WebSocket; Spatial
    EventHandler,
    EventPipeline,
    EventPriority,
    EventType,
    FallbackSpatialIndex,
    GPSDeviationHandler,
    GPSEvent,
    H3SpatialIndex,
    OrderChangeHandler,
    OrderEvent,
    RoutingEvent,
    SpatialEntity,
    TrafficEvent,
    TrafficHandler,
    WebSocketManager,
    create_spatial_index,
    manager as ws_manager,
)

# ============================================================
# Routing sub-package
# ============================================================
from app.services.routing import (
    ClusteringService,
    DistanceBasedClusterer,
    OSRMClient,
    RouteOptimizer,
    clustering_service,
    distance_clusterer,
    osrm_client,
    route_optimizer,
)

# ============================================================
# Security sub-package
# ============================================================
from app.services.security import (
    AnonymizationLevel,
    AnonymizedLocation,
    CoordinateEncryptor,
    GDPRComplianceService,
    GDPRDeletionResult,
    GDPRExportResult,
    GeoAccessAction,
    GeoAccessLog,
    GeoAuditLogger,
    LocationAnonymizer,
    create_security_services,
)

# ============================================================
# Solvers sub-package
# ============================================================
from app.services.solvers import (  # Base classes; FMCG-specific; Selector; Solvers
    Break,
    ClientCategory,
    GAConfig,
    GeneticSolver,
    GreedySolver,
    Job,
    Location,
    ORToolsSolver,
    ProblemFeatures,
    RegionalConfig,
    RegionalConstraints,
    Route,
    RouteSolver,
    RouteStep,
    RoutingProblem,
    SmartSolverSelector,
    SolutionResult,
    SolverFactory,
    SolverType,
    TransportMode,
    VehicleConfig,
    VisitPurpose,
    VROOMSolver,
    solver_selector,
    vroom_solver,
)
from app.services.webhook_service import WebhookService, webhook_service

__all__ = [
    # ========== Solvers ==========
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
    "ClientCategory",
    "VisitPurpose",
    "RegionalConfig",
    "RegionalConstraints",
    "SmartSolverSelector",
    "ProblemFeatures",
    "solver_selector",
    "VROOMSolver",
    "vroom_solver",
    "ORToolsSolver",
    "GeneticSolver",
    "GAConfig",
    "GreedySolver",
    # ========== Routing ==========
    "OSRMClient",
    "osrm_client",
    "RouteOptimizer",
    "route_optimizer",
    "ClusteringService",
    "clustering_service",
    "DistanceBasedClusterer",
    "distance_clusterer",
    # ========== Planning ==========
    "WeeklyPlanner",
    "weekly_planner",
    "ReroutingService",
    "rerouting_service",
    "RerouteResult",
    "PredictiveReroutingEngine",
    "predictive_engine",
    "ScheduleFeasibilityCheck",
    # ========== Caching ==========
    "CacheWarmer",
    "WarmingStrategy",
    "ParallelMatrixComputer",
    "MatrixCache",
    "CachedParallelMatrixComputer",
    # ========== Realtime ==========
    "EventPipeline",
    "EventType",
    "EventPriority",
    "RoutingEvent",
    "GPSEvent",
    "TrafficEvent",
    "OrderEvent",
    "EventHandler",
    "GPSDeviationHandler",
    "TrafficHandler",
    "OrderChangeHandler",
    "WebSocketManager",
    "ws_manager",
    "SpatialEntity",
    "H3SpatialIndex",
    "FallbackSpatialIndex",
    "create_spatial_index",
    # ========== Security ==========
    "CoordinateEncryptor",
    "AnonymizationLevel",
    "AnonymizedLocation",
    "LocationAnonymizer",
    "GeoAccessAction",
    "GeoAccessLog",
    "GeoAuditLogger",
    "GDPRExportResult",
    "GDPRDeletionResult",
    "GDPRComplianceService",
    "create_security_services",
    # ========== PDF Export ==========
    "PDFExporter",
    "pdf_exporter",
    # ========== Webhooks ==========
    "WebhookService",
    "webhook_service",
    # ========== Analytics ==========
    "ServiceTimeCalculator",
    "AgentSkills",
    "SkillBasedAssignment",
    "ClientVisitFeatures",
    "PredictiveVisitFrequency",
    "TrafficProfile",
    "TrafficAwareETA",
    "ETACalibrationData",
    "ETACalibrationService",
    "SmartPriorityRefresh",
    "VisitOutcome",
    "VisitFeedback",
    "VisitFeedbackProcessor",
    "ClientSatisfactionInputs",
    "CustomerSatisfactionScore",
]
