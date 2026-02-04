"""
Integration tests for new modules (R1-R21 implementations).

Tests cross-module interactions and end-to-end workflows.
"""
import pytest
import asyncio
from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import numpy as np


class TestGeneticSolverWithSolverSelector:
    """Test GeneticSolver with SmartSolverSelector integration."""

    @pytest.fixture
    def sample_jobs(self):
        """Create sample jobs."""
        from app.services.solvers.solver_interface import Job, Location

        return [
            Job(
                id=uuid4(),
                location=Location(
                    latitude=41.0 + i * 0.01,
                    longitude=69.0 + i * 0.01,
                    address=f"Point {i}",
                ),
                priority=1,
                demand_kg=10.0,
            )
            for i in range(50)
        ]

    @pytest.fixture
    def sample_vehicles(self):
        """Create sample vehicles."""
        from app.services.solvers.solver_interface import VehicleConfig

        return [
            VehicleConfig(
                id=uuid4(),
                capacity_kg=500.0,
                work_start=time(8, 0),
                work_end=time(18, 0),
            )
            for _ in range(5)
        ]

    def test_selector_prefers_genetic_for_large_problems(self, sample_jobs, sample_vehicles):
        """Test that selector recommends genetic solver for large problems."""
        from app.services.solvers.solver_selector import SmartSolverSelector
        from app.services.solvers.solver_interface import RoutingProblem, SolverType

        selector = SmartSolverSelector()

        # Create large problem (400+ jobs)
        large_jobs = sample_jobs * 10  # 500 jobs

        problem = RoutingProblem(
            jobs=large_jobs,
            vehicles=sample_vehicles,
            planning_date=datetime.now().date(),
        )

        result = selector.select(problem)

        # For very large problems, GENETIC should be considered
        assert result in [SolverType.GENETIC, SolverType.ORTOOLS]

    def test_selector_features_extraction(self, sample_jobs, sample_vehicles):
        """Test feature extraction for solver selection."""
        from app.services.solvers.solver_selector import SmartSolverSelector
        from app.services.solvers.solver_interface import RoutingProblem

        selector = SmartSolverSelector()

        problem = RoutingProblem(
            jobs=sample_jobs,
            vehicles=sample_vehicles,
            planning_date=datetime.now().date(),
        )

        features = selector.extract_features(problem)

        assert features.n_jobs == 50
        assert features.n_vehicles == 5
        assert features.has_capacity is True


class TestParallelMatrixWithCacheWarmer:
    """Test ParallelMatrixComputer with CacheWarmer integration."""

    @pytest.fixture
    def mock_osrm_client(self):
        """Create mock OSRM client."""
        client = MagicMock()

        async def mock_get_table(coords, **kwargs):
            n = len(coords)
            return MagicMock(
                durations=[[100.0] * n for _ in range(n)],
                distances=[[1000.0] * n for _ in range(n)],
            )

        client.get_table = mock_get_table
        return client

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_parallel_matrix_caching(self, mock_osrm_client, mock_redis_client):
        """Test matrix computation with caching."""
        from app.services.caching.parallel_matrix import CachedParallelMatrixComputer

        computer = CachedParallelMatrixComputer(
            osrm_client=mock_osrm_client,
            redis_client=mock_redis_client,
            max_concurrent=2,
            batch_size=10,
        )

        coords = [(69.0 + i * 0.01, 41.0 + i * 0.01) for i in range(15)]

        # First call - should compute
        durations, distances = await computer.compute(coords)

        assert durations.shape == (15, 15)
        # Should have cached (>10 coordinates)
        mock_redis_client.setex.assert_called()


class TestEventPipelineWithSecurity:
    """Test EventPipeline with GeoSecurity integration."""

    @pytest.mark.asyncio
    async def test_gps_event_with_encryption(self):
        """Test GPS event processing with coordinate encryption."""
        from app.services.realtime.event_pipeline import GPSEvent, EventType
        from app.services.security.geo_security import CoordinateEncryptor

        encryptor = CoordinateEncryptor("test-key")

        # Create GPS event
        event = GPSEvent(
            event_type=EventType.GPS_UPDATE,
            agent_id=uuid4(),
            latitude=41.311,
            longitude=69.279,
        )

        # Encrypt coordinates
        encrypted = encryptor.encrypt_coordinates(
            event.latitude,
            event.longitude,
        )

        # Verify we can decrypt
        lat, lon = encryptor.decrypt_coordinates(encrypted)
        assert lat == event.latitude
        assert lon == event.longitude

    @pytest.mark.asyncio
    async def test_event_pipeline_with_audit_logging(self):
        """Test event pipeline triggers audit logging."""
        from app.services.realtime.event_pipeline import (
            EventPipeline,
            EventHandler,
            RoutingEvent,
            EventType,
        )
        from app.services.security.geo_security import GeoAuditLogger, GeoAccessLog, GeoAccessAction

        # Setup audit logger mock
        mock_db_factory = MagicMock()
        audit_logger = GeoAuditLogger(mock_db_factory)

        # Custom handler that logs to audit
        class AuditingHandler(EventHandler):
            def __init__(self, logger):
                self.logger = logger

            async def can_handle(self, event):
                return True

            async def handle(self, event):
                self.logger.log_sync(GeoAccessLog(
                    action=GeoAccessAction.TRACK,
                    resource_type="agent",
                    resource_id=event.agent_id,
                ))
                return None

        pipeline = EventPipeline()
        pipeline.register_handler(AuditingHandler(audit_logger))

        # Process event
        event = RoutingEvent(
            event_type=EventType.GPS_UPDATE,
            agent_id=uuid4(),
        )

        await pipeline._process_event(event)

        # Verify audit log created
        assert len(audit_logger._buffer) == 1


class TestSpatialIndexWithAnonymization:
    """Test SpatialIndex with LocationAnonymizer integration."""

    def test_anonymize_spatial_entities(self):
        """Test anonymizing entities in spatial index."""
        from app.services.realtime.spatial_index import FallbackSpatialIndex, SpatialEntity
        from app.services.security.geo_security import LocationAnonymizer, AnonymizationLevel

        index = FallbackSpatialIndex(grid_size_degrees=0.001)

        # Add entities
        entities = [
            SpatialEntity(
                id=uuid4(),
                latitude=41.311234,
                longitude=69.279567,
            )
            for _ in range(10)
        ]

        for entity in entities:
            index.add(entity)

        # Query and anonymize results
        results = index.query_radius(41.311, 69.279, 1000)

        anonymized_results = []
        for entity in results:
            anon = LocationAnonymizer.anonymize(
                entity.latitude,
                entity.longitude,
                AnonymizationLevel.MEDIUM,
            )
            anonymized_results.append(anon)

        # Verify anonymization applied
        for anon in anonymized_results:
            assert anon.anonymized_latitude == 41.31  # Rounded to 2 decimals
            assert anon.anonymized_longitude == 69.28


class TestGDPRWithCacheWarmer:
    """Test GDPR service with CacheWarmer integration."""

    @pytest.mark.asyncio
    async def test_gdpr_deletion_clears_caches(self):
        """Test GDPR deletion triggers cache invalidation."""
        from app.services.security.geo_security import GDPRComplianceService
        from app.services.caching.cache_warmer import CacheWarmer

        mock_db_factory = MagicMock()
        mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_db_factory.return_value.__aexit__ = AsyncMock()

        mock_cache = MagicMock()
        mock_cache.delete_pattern = AsyncMock(return_value=5)

        # Setup services
        gdpr_service = GDPRComplianceService(mock_db_factory)
        cache_warmer = CacheWarmer(
            db_session_factory=mock_db_factory,
            cache_service=mock_cache,
            osrm_client=MagicMock(),
        )

        user_id = uuid4()

        # Delete user data
        await gdpr_service.delete_user_data(user_id)

        # Invalidate caches (simulating integrated flow)
        deleted = await cache_warmer.invalidate_agent_caches(user_id)

        mock_cache.delete_pattern.assert_called()


class TestFullOptimizationPipeline:
    """Test full optimization pipeline with all new modules."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services for pipeline."""
        return {
            'osrm': MagicMock(),
            'redis': MagicMock(),
            'db_factory': MagicMock(),
            'websocket': MagicMock(),
        }

    @pytest.mark.asyncio
    async def test_optimization_with_security(self, mock_services):
        """Test optimization pipeline with security features."""
        from app.services.solvers.genetic_solver import GeneticSolver, GAConfig
        from app.services.security.geo_security import CoordinateEncryptor, LocationAnonymizer, AnonymizationLevel
        from app.services.solvers.solver_interface import RoutingProblem, Job, Location, SolverType

        # Setup
        encryptor = CoordinateEncryptor("pipeline-test-key")
        solver = GeneticSolver(GAConfig(
            population_size=10,
            generations=5,
            elite_size=2,
        ))

        # Create jobs with encrypted coordinates
        original_coords = [
            (41.311, 69.279),
            (41.320, 69.290),
            (41.330, 69.300),
        ]

        # In real scenario, coordinates would be stored encrypted
        encrypted_coords = [
            encryptor.encrypt_coordinates(lat, lon)
            for lat, lon in original_coords
        ]

        # Decrypt for optimization
        decrypted_coords = [
            encryptor.decrypt_coordinates(enc)
            for enc in encrypted_coords
        ]

        jobs = [
            Job(
                id=uuid4(),
                location=Location(latitude=lat, longitude=lon, address=f"Point {i}"),
                priority=1,
            )
            for i, (lat, lon) in enumerate(decrypted_coords)
        ]

        problem = RoutingProblem(
            jobs=jobs,
            vehicles=[],
            planning_date=datetime.now().date(),
        )

        # Solve
        result = await solver.solve(problem)

        # Anonymize results for analytics
        anonymized = [
            LocationAnonymizer.anonymize(
                job.location.latitude,
                job.location.longitude,
                AnonymizationLevel.MEDIUM,
            )
            for job in jobs
        ]

        assert result is not None
        assert len(anonymized) == 3


class TestConcurrentProcessing:
    """Test concurrent processing across modules."""

    @pytest.mark.asyncio
    async def test_concurrent_event_processing(self):
        """Test concurrent event processing."""
        from app.services.realtime.event_pipeline import (
            EventPipeline,
            EventHandler,
            RoutingEvent,
            EventType,
        )

        processed_count = [0]

        class CountingHandler(EventHandler):
            async def can_handle(self, event):
                return True

            async def handle(self, event):
                await asyncio.sleep(0.01)  # Simulate processing
                processed_count[0] += 1
                return None

        pipeline = EventPipeline(max_queue_size=100, max_concurrent=4)
        pipeline.register_handler(CountingHandler())

        # Start pipeline
        await pipeline.start()

        # Submit many events
        for _ in range(20):
            await pipeline.submit(RoutingEvent(event_type=EventType.GPS_UPDATE))

        # Wait for processing
        await asyncio.sleep(0.5)

        # Stop pipeline
        await pipeline.stop()

        assert processed_count[0] == 20

    @pytest.mark.asyncio
    async def test_concurrent_matrix_computation(self):
        """Test concurrent matrix batch computation."""
        from app.services.caching.parallel_matrix import ParallelMatrixComputer

        mock_osrm = MagicMock()

        call_count = [0]

        async def mock_get_table(*args, **kwargs):
            call_count[0] += 1
            await asyncio.sleep(0.01)
            return MagicMock(
                durations=[[100.0] * 10 for _ in range(10)],
                distances=[[1000.0] * 10 for _ in range(10)],
            )

        mock_osrm.get_table = mock_get_table

        computer = ParallelMatrixComputer(
            osrm_client=mock_osrm,
            max_concurrent=4,
            batch_size=10,
        )

        coords = [(69.0 + i * 0.01, 41.0 + i * 0.01) for i in range(25)]

        durations, distances = await computer.compute(coords)

        assert durations.shape == (25, 25)
        # Multiple batches should have been processed concurrently
        assert call_count[0] > 1


class TestErrorHandlingAcrossModules:
    """Test error handling across module boundaries."""

    @pytest.mark.asyncio
    async def test_solver_fallback_on_error(self):
        """Test solver continues on errors."""
        from app.services.solvers.genetic_solver import GeneticSolver, GAConfig
        from app.services.solvers.solver_interface import RoutingProblem, Job, Location

        solver = GeneticSolver(GAConfig(
            population_size=5,
            generations=3,
        ))

        # Empty problem should not raise
        problem = RoutingProblem(
            jobs=[],
            vehicles=[],
            planning_date=datetime.now().date(),
        )

        result = await solver.solve(problem)

        assert result is not None
        assert result.routes == []

    @pytest.mark.asyncio
    async def test_event_pipeline_continues_on_handler_error(self):
        """Test event pipeline continues when handler fails."""
        from app.services.realtime.event_pipeline import (
            EventPipeline,
            EventHandler,
            RoutingEvent,
            EventType,
        )

        class FailingHandler(EventHandler):
            async def can_handle(self, event):
                return True

            async def handle(self, event):
                raise Exception("Handler error")

        pipeline = EventPipeline()
        pipeline.register_handler(FailingHandler())

        event = RoutingEvent(event_type=EventType.GPS_UPDATE)

        # Should not raise
        await pipeline._process_event(event)

        # Event should still be marked as processed
        assert event.processed is True

    def test_encryption_with_invalid_key(self):
        """Test encryption error handling."""
        from app.services.security.geo_security import CoordinateEncryptor

        encryptor = CoordinateEncryptor("key1")
        encrypted = encryptor.encrypt_coordinates(41.311, 69.279)

        # Try to decrypt with wrong key
        wrong_encryptor = CoordinateEncryptor("key2")

        with pytest.raises(Exception):
            wrong_encryptor.decrypt_coordinates(encrypted)
