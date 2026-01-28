"""
OSRM (Open Source Routing Machine) client for distance matrix calculation.
"""
import asyncio
from dataclasses import dataclass
from typing import Optional

import httpx

from app.core.config import settings


@dataclass
class RouteResult:
    """Result of a route calculation."""
    distance_meters: float
    duration_seconds: float
    geometry: Optional[dict] = None


@dataclass
class MatrixResult:
    """Result of a distance matrix calculation."""
    distances: list[list[float]]  # meters
    durations: list[list[float]]  # seconds


class OSRMClient:
    """
    Client for OSRM routing service.

    OSRM provides fast routing and distance matrix calculations.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.OSRM_URL).rstrip("/")
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    async def get_route(
        self,
        coordinates: list[tuple[float, float]],
        profile: str = "driving",
        geometries: str = "geojson",
        overview: str = "full",
    ) -> RouteResult:
        """
        Get route between coordinates.

        Args:
            coordinates: List of (longitude, latitude) tuples
            profile: Routing profile (driving, walking, cycling)
            geometries: Format for route geometry (geojson, polyline, polyline6)
            overview: Level of detail (full, simplified, false)

        Returns:
            RouteResult with distance, duration, and geometry
        """
        coords_str = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
        url = f"{self.base_url}/route/v1/{profile}/{coords_str}"

        params = {
            "geometries": geometries,
            "overview": overview,
            "steps": "false",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data["code"] != "Ok":
            raise ValueError(f"OSRM error: {data.get('message', 'Unknown error')}")

        route = data["routes"][0]
        return RouteResult(
            distance_meters=route["distance"],
            duration_seconds=route["duration"],
            geometry=route.get("geometry"),
        )

    async def get_table(
        self,
        coordinates: list[tuple[float, float]],
        profile: str = "driving",
        sources: Optional[list[int]] = None,
        destinations: Optional[list[int]] = None,
        use_cache: bool = True,
    ) -> MatrixResult:
        """
        Get distance/duration matrix between coordinates.

        Args:
            coordinates: List of (longitude, latitude) tuples
            profile: Routing profile
            sources: Indices of source points (default: all)
            destinations: Indices of destination points (default: all)
            use_cache: Whether to use cache (default: True)

        Returns:
            MatrixResult with distances and durations matrices
        """
        # Try cache first (only for full matrix requests)
        if use_cache and sources is None and destinations is None:
            from app.core.cache import distance_matrix_cache
            cached = await distance_matrix_cache.get(coordinates)
            if cached:
                return MatrixResult(
                    distances=cached["distances"],
                    durations=cached["durations"],
                )

        coords_str = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
        url = f"{self.base_url}/table/v1/{profile}/{coords_str}"

        params = {
            "annotations": "distance,duration",
        }

        if sources is not None:
            params["sources"] = ";".join(map(str, sources))
        if destinations is not None:
            params["destinations"] = ";".join(map(str, destinations))

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data["code"] != "Ok":
            raise ValueError(f"OSRM error: {data.get('message', 'Unknown error')}")

        result = MatrixResult(
            distances=data["distances"],
            durations=data["durations"],
        )

        # Cache the result (only for full matrix requests)
        if use_cache and sources is None and destinations is None:
            from app.core.cache import distance_matrix_cache
            await distance_matrix_cache.set(
                coordinates,
                {"distances": result.distances, "durations": result.durations},
            )

        return result

    async def get_nearest(
        self,
        longitude: float,
        latitude: float,
        profile: str = "driving",
        number: int = 1,
    ) -> list[dict]:
        """
        Find nearest road point to a coordinate.

        Args:
            longitude: Longitude
            latitude: Latitude
            profile: Routing profile
            number: Number of results to return

        Returns:
            List of nearest points with location and distance
        """
        url = f"{self.base_url}/nearest/v1/{profile}/{longitude},{latitude}"

        params = {"number": number}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data["code"] != "Ok":
            raise ValueError(f"OSRM error: {data.get('message', 'Unknown error')}")

        return data["waypoints"]

    async def health_check(self) -> bool:
        """Check if OSRM service is available."""
        try:
            url = f"{self.base_url}/health"
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception:
            # Try a simple route request as fallback
            try:
                # Tashkent coordinates
                await self.get_nearest(69.279737, 41.311081)
                return True
            except Exception:
                return False


# Singleton instance
osrm_client = OSRMClient()
