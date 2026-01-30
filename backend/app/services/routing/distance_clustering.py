"""
Distance-based clustering using OSRM real road distances.

Replaces Euclidean-based K-means with hierarchical clustering
based on actual travel times for more accurate territory planning.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from app.models.client import Client
from app.services.routing.osrm_client import MatrixResult, osrm_client

logger = logging.getLogger(__name__)


@dataclass
class ClusterResult:
    """Result of clustering operation."""

    clusters: dict[int, list[UUID]]  # cluster_id -> list of client IDs
    cluster_centers: dict[int, tuple[float, float]]  # cluster_id -> (lat, lon)
    total_clients: int
    num_clusters: int
    avg_cluster_size: float
    cluster_distances: dict[int, float]  # cluster_id -> avg internal distance


class DistanceBasedClusterer:
    """
    Cluster clients based on actual travel distances from OSRM.

    Uses hierarchical clustering with Ward's method for
    compact, geographically coherent clusters.

    Benefits over K-means with Euclidean distances:
    - Accounts for road network topology
    - Better for areas with rivers, highways, restricted zones
    - More accurate travel time estimates
    """

    def __init__(self, use_duration: bool = True):
        """
        Initialize clusterer.

        Args:
            use_duration: Use travel duration instead of distance.
                         Duration is usually better for planning.
        """
        self.use_duration = use_duration

    async def cluster_clients(
        self,
        clients: list[Client],
        n_clusters: int = 5,
        max_cluster_size: Optional[int] = None,
    ) -> ClusterResult:
        """
        Cluster clients based on real road distances.

        Args:
            clients: List of clients to cluster
            n_clusters: Target number of clusters
            max_cluster_size: Maximum clients per cluster (for load balancing)

        Returns:
            ClusterResult with cluster assignments
        """
        if not clients:
            return ClusterResult(
                clusters={},
                cluster_centers={},
                total_clients=0,
                num_clusters=0,
                avg_cluster_size=0,
                cluster_distances={},
            )

        if len(clients) <= n_clusters:
            # Fewer clients than clusters - each client is its own cluster
            clusters = {i: [c.id] for i, c in enumerate(clients)}
            centers = {i: (float(c.latitude), float(c.longitude)) for i, c in enumerate(clients)}
            return ClusterResult(
                clusters=clusters,
                cluster_centers=centers,
                total_clients=len(clients),
                num_clusters=len(clients),
                avg_cluster_size=1.0,
                cluster_distances={i: 0.0 for i in range(len(clients))},
            )

        # Get distance matrix from OSRM
        logger.info(f"Fetching OSRM distance matrix for {len(clients)} clients")
        matrix = await self._get_distance_matrix(clients)

        # Use duration or distance
        if self.use_duration:
            distance_matrix = np.array(matrix.durations)
        else:
            distance_matrix = np.array(matrix.distances)

        # Handle any null values (unreachable points)
        distance_matrix = np.nan_to_num(
            distance_matrix,
            nan=np.nanmax(distance_matrix) * 2 if np.any(~np.isnan(distance_matrix)) else 999999,
        )

        # Make symmetric (OSRM can return asymmetric matrices)
        distance_matrix = (distance_matrix + distance_matrix.T) / 2

        # Set diagonal to 0
        np.fill_diagonal(distance_matrix, 0)

        # Perform hierarchical clustering
        labels = self._hierarchical_cluster(
            distance_matrix,
            n_clusters,
            max_cluster_size,
        )

        # Build cluster result
        clusters = self._build_clusters(clients, labels)
        centers = self._compute_cluster_centers(clients, clusters)
        cluster_distances = self._compute_cluster_distances(clients, clusters, distance_matrix)

        result = ClusterResult(
            clusters=clusters,
            cluster_centers=centers,
            total_clients=len(clients),
            num_clusters=len(clusters),
            avg_cluster_size=len(clients) / len(clusters) if clusters else 0,
            cluster_distances=cluster_distances,
        )

        logger.info(f"Clustering complete: {len(clusters)} clusters, " f"avg size {result.avg_cluster_size:.1f}")

        return result

    async def _get_distance_matrix(
        self,
        clients: list[Client],
    ) -> MatrixResult:
        """Fetch distance matrix from OSRM."""
        coordinates = [(float(c.longitude), float(c.latitude)) for c in clients]

        # Use batched method for large sets
        if len(coordinates) > 100:
            return await osrm_client.get_table_batched(coordinates)
        else:
            return await osrm_client.get_table(coordinates)

    def _hierarchical_cluster(
        self,
        distance_matrix: np.ndarray,
        n_clusters: int,
        max_cluster_size: Optional[int] = None,
    ) -> np.ndarray:
        """
        Perform hierarchical clustering.

        Uses Ward's method for compact clusters.
        """
        # Convert to condensed form for scipy
        # scipy expects upper triangle in condensed form
        condensed = squareform(distance_matrix, checks=False)

        # Perform hierarchical clustering
        # Ward's method minimizes within-cluster variance
        Z = linkage(condensed, method="ward")

        # Cut dendrogram to get clusters
        labels = fcluster(Z, n_clusters, criterion="maxclust")

        # Adjust if max_cluster_size specified
        if max_cluster_size:
            labels = self._split_large_clusters(labels, distance_matrix, max_cluster_size)

        return labels

    def _split_large_clusters(
        self,
        labels: np.ndarray,
        distance_matrix: np.ndarray,
        max_size: int,
    ) -> np.ndarray:
        """Split clusters that exceed max size."""
        from collections import Counter

        cluster_counts = Counter(labels)
        next_label = max(labels) + 1

        for cluster_id, count in cluster_counts.items():
            if count <= max_size:
                continue

            # Find indices in this cluster
            indices = np.where(labels == cluster_id)[0]

            # Sub-cluster using the same method
            sub_matrix = distance_matrix[np.ix_(indices, indices)]
            n_sub = max(2, count // max_size + 1)

            try:
                condensed = squareform(sub_matrix, checks=False)
                Z = linkage(condensed, method="ward")
                sub_labels = fcluster(Z, n_sub, criterion="maxclust")

                # Assign new labels
                for i, idx in enumerate(indices):
                    if sub_labels[i] > 1:  # Keep first sub-cluster with original label
                        labels[idx] = next_label + sub_labels[i] - 2

                next_label += n_sub - 1
            except Exception as e:
                logger.warning(f"Failed to split cluster {cluster_id}: {e}")

        return labels

    def _build_clusters(
        self,
        clients: list[Client],
        labels: np.ndarray,
    ) -> dict[int, list[UUID]]:
        """Build cluster dictionary from labels."""
        clusters: dict[int, list[UUID]] = defaultdict(list)

        for client, label in zip(clients, labels):
            clusters[int(label)].append(client.id)

        return dict(clusters)

    def _compute_cluster_centers(
        self,
        clients: list[Client],
        clusters: dict[int, list[UUID]],
    ) -> dict[int, tuple[float, float]]:
        """Compute centroid of each cluster."""
        client_map = {c.id: c for c in clients}
        centers = {}

        for cluster_id, client_ids in clusters.items():
            cluster_clients = [client_map[cid] for cid in client_ids]
            lat = sum(float(c.latitude) for c in cluster_clients) / len(cluster_clients)
            lon = sum(float(c.longitude) for c in cluster_clients) / len(cluster_clients)
            centers[cluster_id] = (lat, lon)

        return centers

    def _compute_cluster_distances(
        self,
        clients: list[Client],
        clusters: dict[int, list[UUID]],
        distance_matrix: np.ndarray,
    ) -> dict[int, float]:
        """Compute average internal distance for each cluster."""
        client_index = {c.id: i for i, c in enumerate(clients)}
        cluster_distances = {}

        for cluster_id, client_ids in clusters.items():
            if len(client_ids) < 2:
                cluster_distances[cluster_id] = 0.0
                continue

            indices = [client_index[cid] for cid in client_ids]
            sub_matrix = distance_matrix[np.ix_(indices, indices)]

            # Average of non-diagonal elements
            n = len(indices)
            total = sub_matrix.sum() - np.trace(sub_matrix)
            avg = total / (n * (n - 1)) if n > 1 else 0

            cluster_distances[cluster_id] = float(avg)

        return cluster_distances

    async def assign_to_agents(
        self,
        clients: list[Client],
        agent_ids: list[UUID],
        balance_workload: bool = True,
    ) -> dict[UUID, list[UUID]]:
        """
        Cluster clients and assign clusters to agents.

        Args:
            clients: Clients to assign
            agent_ids: Available agent IDs
            balance_workload: Try to balance number of clients per agent

        Returns:
            Dict mapping agent_id to list of client_ids
        """
        n_agents = len(agent_ids)
        if n_agents == 0:
            return {}

        # Cluster into agent count
        result = await self.cluster_clients(
            clients,
            n_clusters=n_agents,
            max_cluster_size=len(clients) // n_agents + 10 if balance_workload else None,
        )

        # Assign clusters to agents
        # Sort clusters by size for better balance
        sorted_clusters = sorted(
            result.clusters.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )

        assignments: dict[UUID, list[UUID]] = {aid: [] for aid in agent_ids}
        agent_loads = {aid: 0 for aid in agent_ids}

        for cluster_id, client_ids in sorted_clusters:
            # Assign to agent with lowest load
            min_agent = min(agent_loads.keys(), key=lambda a: agent_loads[a])
            assignments[min_agent].extend(client_ids)
            agent_loads[min_agent] += len(client_ids)

        logger.info(
            f"Assigned {len(clients)} clients to {n_agents} agents, " f"loads: {[len(v) for v in assignments.values()]}"
        )

        return assignments


# Singleton instance
distance_clusterer = DistanceBasedClusterer()
