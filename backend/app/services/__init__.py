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

# ============================================================
# Solvers sub-package
# ============================================================
from app.services.solvers import (
    # Base classes
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
    # FMCG-specific
    ClientCategory,
    VisitPurpose,
    RegionalConfig,
    RegionalConstraints,
    # Selector
    SmartSolverSelector,
    ProblemFeatures,
    solver_selector,
    # Solvers
    VROOMSolver,
    vroom_solver,
    ORToolsSolver,
    GeneticSolver,
    GAConfig,
    GreedySolver,
)

# ============================================================
# Routing sub-package
# ============================================================
from app.services.routing import (
    OSRMClient,
    osrm_client,
    RouteOptimizer,
    route_optimizer,
    Clusterer,
    DistanceBasedClusterer,
    distance_clusterer,
)

# ============================================================
# Planning sub-package
# ============================================================
from app.services.planning import (
    WeeklyPlanner,
    weekly_planner,
    ReroutingService,
    rerouting_service,
    PredictiveReroutingEngine,
    predictive_engine,
    ScheduleFeasibilityCheck,
)

# ============================================================
# Caching sub-package
# ============================================================
from app.services.caching import (
    CacheWarmer,
    WarmingStrategy,
    ParallelMatrixComputer,
    MatrixCache,
    CachedParallelMatrixComputer,
)

# ============================================================
# Realtime sub-package
# ============================================================
from app.services.realtime import (
    # Event pipeline
    EventPipeline,
    EventType,
    EventPriority,
    BaseEvent,
    GPSEvent,
    TrafficEvent,
    OrderEvent,
    VisitEvent,
    EventHandler,
    GPSUpdateHandler,
    TrafficAlertHandler,
    OrderCancelHandler,
    VisitCompleteHandler,
    # WebSocket
    WebSocketManager,
    ws_manager,
    # Spatial
    SpatialEntity,
    H3SpatialIndex,
    FallbackSpatialIndex,
    create_spatial_index,
)

# ============================================================
# Security sub-package
# ============================================================
from app.services.security import (
    CoordinateEncryptor,
    AnonymizationLevel,
    AnonymizedLocation,
    LocationAnonymizer,
    GeoAccessAction,
    GeoAccessLog,
    GeoAuditLogger,
    GDPRExportResult,
    GDPRDeletionResult,
    GDPRComplianceService,
    create_security_services,
)

# ============================================================
# Root-level services
# ============================================================
from app.services.pdf_export import PDFExporter, pdf_exporter
from app.services.webhook_service import WebhookService, webhook_service

# Analytics (many classes, import selectively)
from app.services.analytics import (
    ServiceTimeCalculator,
    AgentSkills,
    SkillBasedAssignment,
    ClientVisitFeatures,
    PredictiveVisitFrequency,
    TrafficProfile,
    TrafficAwareETA,
    ETACalibrationData,
    ETACalibrationService,
    SmartPriorityRefresh,
    VisitOutcome,
    VisitFeedback,
    VisitFeedbackProcessor,
    ClientSatisfactionInputs,
    CustomerSatisfactionScore,
)

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
    "Clusterer",
    "DistanceBasedClusterer",
    "distance_clusterer",
    # ========== Planning ==========
    "WeeklyPlanner",
    "weekly_planner",
    "ReroutingService",
    "rerouting_service",
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
    "BaseEvent",
    "GPSEvent",
    "TrafficEvent",
    "OrderEvent",
    "VisitEvent",
    "EventHandler",
    "GPSUpdateHandler",
    "TrafficAlertHandler",
    "OrderCancelHandler",
    "VisitCompleteHandler",
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
