"""
Routing sub-package.

Contains core routing services:
- OSRM client for distance matrices
- Route optimizer
- Clustering algorithms
"""

from app.services.routing.clustering import Clusterer
from app.services.routing.distance_clustering import (
    DistanceBasedClusterer,
    distance_clusterer,
)
from app.services.routing.osrm_client import OSRMClient, osrm_client
from app.services.routing.route_optimizer import RouteOptimizer, route_optimizer

__all__ = [
    "OSRMClient",
    "osrm_client",
    "RouteOptimizer",
    "route_optimizer",
    "Clusterer",
    "DistanceBasedClusterer",
    "distance_clusterer",
]
