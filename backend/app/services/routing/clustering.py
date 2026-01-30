"""
Advanced clustering service for route optimization.

Provides multiple clustering strategies:
- K-means (Euclidean) - fast, baseline
- Hierarchical (OSRM distances) - accurate, considers real roads
- Agglomerative with time-based distances - for time-window constraints
"""
import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Protocol
from uuid import UUID

import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

from app.core.config import settings


class HasCoordinates(Protocol):
    """Protocol for objects with coordinates."""
    latitude: float
    longitude: float
    id: UUID


@dataclass
class ClusterResult:
    """Result of clustering operation."""
    clusters: dict[int, list[int]]  # cluster_id -> list of item indices
    n_clusters: int
    method: str
    quality_score: float  # Silhouette score or similar


class ClusteringService:
    """
    Advanced clustering service for geographic points.
    
    Supports multiple strategies for different use cases:
    - 'kmeans': Fast, good for evenly distributed points
    - 'hierarchical': Uses OSRM distances, better for road networks
    - 'balanced': Hierarchical with load balancing
    """

    def __init__(self, osrm_client=None):
        from app.services.osrm_client import osrm_client as default_osrm
        self.osrm = osrm_client or default_osrm

    async def cluster_kmeans(
        self,
        items: list[HasCoordinates],
        n_clusters: int = 5,
    ) -> ClusterResult:
        """
        K-means clustering using Euclidean distance.
        
        Fast but doesn't consider road network.
        Best for: initial planning, evenly distributed areas.
        """
        from sklearn.cluster import KMeans

        if len(items) < n_clusters:
            return ClusterResult(
                clusters={0: list(range(len(items)))},
                n_clusters=1,
                method="kmeans",
                quality_score=1.0,
            )

        coords = np.array([
            [float(item.latitude), float(item.longitude)]
            for item in items
        ])

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(coords)

        clusters = self._labels_to_clusters(labels)
        quality = self._calculate_quality(coords, labels)

        return ClusterResult(
            clusters=clusters,
            n_clusters=n_clusters,
            method="kmeans",
            quality_score=quality,
        )

    async def cluster_hierarchical_osrm(
        self,
        items: list[HasCoordinates],
        n_clusters: int = 5,
        use_cache: bool = True,
    ) -> ClusterResult:
        """
        Hierarchical clustering using OSRM road distances.
        
        More accurate for route optimization as it considers
        actual road network, not straight-line distances.
        
        Best for: daily route planning, delivery optimization.
        """
        if len(items) < n_clusters:
            return ClusterResult(
                clusters={0: list(range(len(items)))},
                n_clusters=1,
                method="hierarchical_osrm",
                quality_score=1.0,
            )

        # Get coordinates for OSRM (lon, lat format)
        coordinates = [
            (float(item.longitude), float(item.latitude))
            for item in items
        ]

        try:
            # Get distance matrix from OSRM
            matrix_result = await self.osrm.get_table(
                coordinates,
                use_cache=use_cache,
            )
            
            # Use duration matrix (better reflects actual travel cost)
            distance_matrix = np.array(matrix_result.durations)
            
            # Handle None values (unreachable points)
            distance_matrix = np.nan_to_num(distance_matrix, nan=1e9)
            
            # Make symmetric (average of both directions)
            distance_matrix = (distance_matrix + distance_matrix.T) / 2
            
            # Set diagonal to 0
            np.fill_diagonal(distance_matrix, 0)

        except Exception as e:
            # Fallback to Euclidean if OSRM fails
            print(f"OSRM failed, falling back to Euclidean: {e}")
            return await self.cluster_kmeans(items, n_clusters)

        # Convert to condensed form for scipy
        condensed = squareform(distance_matrix)

        # Hierarchical clustering with Ward's method
        Z = linkage(condensed, method='ward')

        # Cut tree to get n_clusters
        labels = fcluster(Z, n_clusters, criterion='maxclust') - 1  # 0-indexed

        clusters = self._labels_to_clusters(labels)
        quality = self._calculate_quality_from_matrix(distance_matrix, labels)

        return ClusterResult(
            clusters=clusters,
            n_clusters=n_clusters,
            method="hierarchical_osrm",
            quality_score=quality,
        )

    async def cluster_balanced(
        self,
        items: list[HasCoordinates],
        n_clusters: int = 5,
        max_per_cluster: int = 30,
        use_cache: bool = True,
    ) -> ClusterResult:
        """
        Balanced clustering ensuring similar cluster sizes.
        
        Uses OSRM distances with post-processing to balance
        the number of items per cluster.
        
        Best for: weekly planning with workload balancing.
        """
        # First, get hierarchical clusters
        result = await self.cluster_hierarchical_osrm(
            items, n_clusters, use_cache
        )

        # Balance clusters
        balanced_clusters = self._balance_clusters(
            result.clusters,
            max_per_cluster,
        )

        return ClusterResult(
            clusters=balanced_clusters,
            n_clusters=len(balanced_clusters),
            method="balanced_osrm",
            quality_score=result.quality_score,
        )

    def _labels_to_clusters(self, labels: np.ndarray) -> dict[int, list[int]]:
        """Convert label array to cluster dictionary."""
        clusters: dict[int, list[int]] = {}
        for idx, label in enumerate(labels):
            label = int(label)
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(idx)
        return clusters

    def _balance_clusters(
        self,
        clusters: dict[int, list[int]],
        max_per_cluster: int,
    ) -> dict[int, list[int]]:
        """
        Balance cluster sizes by redistributing items.
        
        Moves items from oversized clusters to undersized ones.
        """
        # Calculate target size
        total_items = sum(len(c) for c in clusters.values())
        n_clusters = len(clusters)
        target_size = total_items // n_clusters

        # Find over and under filled clusters
        overfilled = {
            k: v for k, v in clusters.items()
            if len(v) > max_per_cluster
        }
        underfilled = {
            k: v for k, v in clusters.items()
            if len(v) < target_size * 0.7
        }

        # Redistribute
        for over_id, over_items in overfilled.items():
            excess = over_items[max_per_cluster:]
            clusters[over_id] = over_items[:max_per_cluster]

            for item in excess:
                # Find cluster with most capacity
                min_cluster = min(
                    clusters.keys(),
                    key=lambda k: len(clusters[k])
                )
                clusters[min_cluster].append(item)

        return clusters

    def _calculate_quality(
        self,
        coords: np.ndarray,
        labels: np.ndarray,
    ) -> float:
        """Calculate clustering quality using silhouette score."""
        from sklearn.metrics import silhouette_score

        if len(set(labels)) < 2:
            return 1.0

        try:
            return float(silhouette_score(coords, labels))
        except Exception:
            return 0.5

    def _calculate_quality_from_matrix(
        self,
        distance_matrix: np.ndarray,
        labels: np.ndarray,
    ) -> float:
        """Calculate quality from precomputed distance matrix."""
        from sklearn.metrics import silhouette_score

        if len(set(labels)) < 2:
            return 1.0

        try:
            return float(silhouette_score(
                distance_matrix,
                labels,
                metric='precomputed'
            ))
        except Exception:
            return 0.5


# Global instance
clustering_service = ClusteringService()


async def cluster_clients_for_week(
    clients: list,
    n_days: int = 5,
    use_osrm: bool = True,
    max_per_day: int = 30,
) -> dict[int, list]:
    """
    Convenience function to cluster clients for weekly planning.
    
    Args:
        clients: List of client objects with lat/lon
        n_days: Number of working days
        use_osrm: Whether to use OSRM distances
        max_per_day: Maximum clients per day
        
    Returns:
        Dict mapping day index to list of clients
    """
    service = ClusteringService()

    if use_osrm:
        result = await service.cluster_balanced(
            clients,
            n_clusters=n_days,
            max_per_cluster=max_per_day,
        )
    else:
        result = await service.cluster_kmeans(clients, n_clusters=n_days)

    # Map cluster indices back to clients
    day_assignments = {}
    for cluster_id, indices in result.clusters.items():
        day = cluster_id % n_days
        if day not in day_assignments:
            day_assignments[day] = []
        day_assignments[day].extend([clients[i] for i in indices])

    return day_assignments
