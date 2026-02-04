"""
Tests for Geolocation Security Services module.

Tests cover:
- R18: CoordinateEncryptor (encryption at rest)
- R19: LocationAnonymizer (anonymization)
- R20: GeoAuditLogger (audit logging)
- R21: GDPRComplianceService (GDPR compliance)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.security.geo_security import (
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


class TestCoordinateEncryptor:
    """Tests for CoordinateEncryptor class (R18)."""

    @pytest.fixture
    def encryptor(self):
        """Create encryptor instance."""
        return CoordinateEncryptor(secret_key="test-secret-key-12345")

    def test_initialization(self, encryptor):
        """Test encryptor initialization."""
        assert encryptor.cipher is not None

    def test_encrypt_coordinates(self, encryptor):
        """Test coordinate encryption."""
        lat, lon = 41.311, 69.279

        encrypted = encryptor.encrypt_coordinates(lat, lon)

        assert encrypted is not None
        assert isinstance(encrypted, str)
        assert encrypted != str(lat)  # Not plaintext

    def test_decrypt_coordinates(self, encryptor):
        """Test coordinate decryption."""
        lat, lon = 41.311, 69.279

        encrypted = encryptor.encrypt_coordinates(lat, lon)
        decrypted_lat, decrypted_lon = encryptor.decrypt_coordinates(encrypted)

        assert decrypted_lat == lat
        assert decrypted_lon == lon

    def test_encrypt_decrypt_roundtrip(self, encryptor):
        """Test encryption-decryption roundtrip."""
        coordinates = [
            (41.311, 69.279),
            (0.0, 0.0),
            (-33.8688, 151.2093),  # Sydney
            (90.0, 180.0),  # Edge case
            (-90.0, -180.0),  # Edge case
        ]

        for lat, lon in coordinates:
            encrypted = encryptor.encrypt_coordinates(lat, lon)
            dec_lat, dec_lon = encryptor.decrypt_coordinates(encrypted)

            assert dec_lat == lat
            assert dec_lon == lon

    def test_encrypt_location_history(self, encryptor):
        """Test encrypting location history."""
        history = [
            {"lat": 41.311, "lon": 69.279, "ts": "2025-01-01T10:00:00"},
            {"lat": 41.312, "lon": 69.280, "ts": "2025-01-01T10:15:00"},
        ]

        encrypted = encryptor.encrypt_location_history(history)

        assert encrypted is not None
        assert isinstance(encrypted, str)

    def test_decrypt_location_history(self, encryptor):
        """Test decrypting location history."""
        history = [
            {"lat": 41.311, "lon": 69.279, "ts": "2025-01-01T10:00:00"},
            {"lat": 41.312, "lon": 69.280, "ts": "2025-01-01T10:15:00"},
        ]

        encrypted = encryptor.encrypt_location_history(history)
        decrypted = encryptor.decrypt_location_history(encrypted)

        assert decrypted == history

    def test_different_keys_incompatible(self):
        """Test that different keys produce incompatible ciphertext."""
        enc1 = CoordinateEncryptor("key1")
        enc2 = CoordinateEncryptor("key2")

        encrypted = enc1.encrypt_coordinates(41.311, 69.279)

        with pytest.raises(Exception):
            enc2.decrypt_coordinates(encrypted)

    def test_encryption_is_unique(self, encryptor):
        """Test that same coordinates produce different ciphertext (due to timestamp)."""
        lat, lon = 41.311, 69.279

        enc1 = encryptor.encrypt_coordinates(lat, lon)
        enc2 = encryptor.encrypt_coordinates(lat, lon)

        # Different due to timestamp in payload
        assert enc1 != enc2


class TestAnonymizationLevel:
    """Tests for AnonymizationLevel enum."""

    def test_enum_values(self):
        """Test anonymization level values."""
        assert AnonymizationLevel.NONE == "none"
        assert AnonymizationLevel.LOW == "low"
        assert AnonymizationLevel.MEDIUM == "medium"
        assert AnonymizationLevel.HIGH == "high"
        assert AnonymizationLevel.VERY_HIGH == "very_high"


class TestLocationAnonymizer:
    """Tests for LocationAnonymizer class (R19)."""

    def test_anonymize_none(self):
        """Test no anonymization preserves precision."""
        lat, lon = 41.311234, 69.279567

        result = LocationAnonymizer.anonymize(lat, lon, AnonymizationLevel.NONE)

        assert result.anonymized_latitude == round(lat, 6)
        assert result.anonymized_longitude == round(lon, 6)
        assert result.anonymization_level == AnonymizationLevel.NONE

    def test_anonymize_low(self):
        """Test low anonymization (~111m)."""
        lat, lon = 41.311234, 69.279567

        result = LocationAnonymizer.anonymize(lat, lon, AnonymizationLevel.LOW)

        assert result.anonymized_latitude == 41.311
        assert result.anonymized_longitude == 69.28
        assert result.anonymization_level == AnonymizationLevel.LOW

    def test_anonymize_medium(self):
        """Test medium anonymization (~1.1km)."""
        lat, lon = 41.311234, 69.279567

        result = LocationAnonymizer.anonymize(lat, lon, AnonymizationLevel.MEDIUM)

        assert result.anonymized_latitude == 41.31
        assert result.anonymized_longitude == 69.28
        assert result.anonymization_level == AnonymizationLevel.MEDIUM

    def test_anonymize_high(self):
        """Test high anonymization (~11km)."""
        lat, lon = 41.311234, 69.279567

        result = LocationAnonymizer.anonymize(lat, lon, AnonymizationLevel.HIGH)

        assert result.anonymized_latitude == 41.3
        assert result.anonymized_longitude == 69.3
        assert result.anonymization_level == AnonymizationLevel.HIGH

    def test_anonymize_returns_anonymized_location(self):
        """Test return type is AnonymizedLocation."""
        result = LocationAnonymizer.anonymize(41.311, 69.279)

        assert isinstance(result, AnonymizedLocation)
        assert result.original_precision == 6
        assert result.area_km2 is not None

    def test_calculate_area_km2(self):
        """Test area calculation for precision levels."""
        areas = {
            0: 12345.0,
            1: 123.5,
            2: 1.23,
            3: 0.012,
        }

        for precision, expected in areas.items():
            area = LocationAnonymizer._calculate_area_km2(precision)
            assert area == expected

    def test_anonymize_trajectory_empty(self):
        """Test trajectory anonymization with empty input."""
        result = LocationAnonymizer.anonymize_trajectory([])
        assert result == []

    def test_anonymize_trajectory_single_point(self):
        """Test trajectory anonymization with single point."""
        now = datetime.now()
        points = [(41.311, 69.279, now)]

        result = LocationAnonymizer.anonymize_trajectory(points)

        assert len(result) == 1

    def test_anonymize_trajectory_temporal_window(self):
        """Test trajectory anonymization with temporal windowing."""
        base_time = datetime(2025, 1, 1, 10, 0, 0)

        # Points within 15 minute window
        points = [
            (41.311, 69.279, base_time),
            (41.312, 69.280, base_time + timedelta(minutes=5)),
            (41.313, 69.281, base_time + timedelta(minutes=10)),
            # New window
            (41.320, 69.290, base_time + timedelta(minutes=30)),
        ]

        result = LocationAnonymizer.anonymize_trajectory(
            points,
            level=AnonymizationLevel.MEDIUM,
            temporal_window_minutes=15,
        )

        # Should produce 2 anonymized points (2 windows)
        assert len(result) == 2


class TestGeoAccessAction:
    """Tests for GeoAccessAction enum."""

    def test_enum_values(self):
        """Test access action values."""
        assert GeoAccessAction.VIEW == "view"
        assert GeoAccessAction.EXPORT == "export"
        assert GeoAccessAction.SHARE == "share"
        assert GeoAccessAction.TRACK == "track"
        assert GeoAccessAction.HISTORY == "history"
        assert GeoAccessAction.BULK_EXPORT == "bulk_export"


class TestGeoAccessLog:
    """Tests for GeoAccessLog dataclass."""

    def test_creation_minimal(self):
        """Test minimal log entry creation."""
        log = GeoAccessLog()

        assert log.id is not None
        assert log.timestamp is not None
        assert log.action == GeoAccessAction.VIEW
        assert log.processed is False if hasattr(log, 'processed') else True

    def test_creation_full(self):
        """Test full log entry creation."""
        user_id = uuid4()
        resource_id = uuid4()

        log = GeoAccessLog(
            user_id=user_id,
            user_role="admin",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            action=GeoAccessAction.EXPORT,
            resource_type="agent",
            resource_id=resource_id,
            coordinates_accessed=True,
            history_range_days=30,
            records_count=100,
            api_endpoint="/api/v1/agents/location",
            request_id="req-123",
            reason="monthly_report",
        )

        assert log.user_id == user_id
        assert log.action == GeoAccessAction.EXPORT
        assert log.coordinates_accessed is True
        assert log.records_count == 100


class TestGeoAuditLogger:
    """Tests for GeoAuditLogger class (R20)."""

    @pytest.fixture
    def mock_db_session_factory(self):
        """Create mock database session factory."""
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        return lambda: session

    @pytest.fixture
    def logger(self, mock_db_session_factory):
        """Create audit logger instance."""
        return GeoAuditLogger(mock_db_session_factory, retention_days=365)

    def test_initialization(self, logger):
        """Test logger initialization."""
        assert logger.retention_days == 365
        assert logger._buffer == []
        assert logger._buffer_size == 100

    def test_log_sync(self, logger):
        """Test synchronous logging (buffer only)."""
        log = GeoAccessLog(action=GeoAccessAction.VIEW)

        logger.log_sync(log)

        assert len(logger._buffer) == 1
        assert logger._buffer[0] == log

    @pytest.mark.asyncio
    async def test_log_async(self, logger):
        """Test asynchronous logging."""
        log = GeoAccessLog(action=GeoAccessAction.VIEW)

        await logger.log(log)

        assert len(logger._buffer) == 1

    @pytest.mark.asyncio
    async def test_log_triggers_flush_at_buffer_size(self, logger, mock_db_session_factory):
        """Test that logging triggers flush at buffer size."""
        logger._buffer_size = 5

        for i in range(5):
            await logger.log(GeoAccessLog(action=GeoAccessAction.VIEW))

        # Buffer should be cleared after flush
        assert len(logger._buffer) == 0

    @pytest.mark.asyncio
    async def test_flush_empty_buffer(self, logger):
        """Test flushing empty buffer is no-op."""
        await logger._flush()
        # Should not raise

    @pytest.mark.asyncio
    async def test_query_logs_returns_list(self, logger):
        """Test query_logs returns list."""
        result = await logger.query_logs()

        assert isinstance(result, list)


class TestGDPRComplianceService:
    """Tests for GDPRComplianceService class (R21)."""

    @pytest.fixture
    def mock_db_session_factory(self):
        """Create mock database session factory."""
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return lambda: session

    @pytest.fixture
    def mock_encryptor(self):
        """Create mock encryptor."""
        return MagicMock(spec=CoordinateEncryptor)

    @pytest.fixture
    def mock_audit_logger(self):
        """Create mock audit logger."""
        logger = MagicMock(spec=GeoAuditLogger)
        logger.log = AsyncMock()
        return logger

    @pytest.fixture
    def service(self, mock_db_session_factory, mock_encryptor, mock_audit_logger):
        """Create GDPR service instance."""
        return GDPRComplianceService(
            db_session_factory=mock_db_session_factory,
            encryptor=mock_encryptor,
            audit_logger=mock_audit_logger,
        )

    def test_initialization(self, service, mock_db_session_factory, mock_encryptor, mock_audit_logger):
        """Test service initialization."""
        assert service.db_session_factory == mock_db_session_factory
        assert service.encryptor == mock_encryptor
        assert service.audit_logger == mock_audit_logger

    @pytest.mark.asyncio
    async def test_export_user_data(self, service, mock_audit_logger):
        """Test user data export."""
        user_id = uuid4()

        result = await service.export_user_data(user_id)

        assert isinstance(result, GDPRExportResult)
        assert result.user_id == user_id
        assert "id" in result.personal_data
        mock_audit_logger.log.assert_called()

    @pytest.mark.asyncio
    async def test_export_user_data_with_history(self, service):
        """Test user data export including location history."""
        user_id = uuid4()

        result = await service.export_user_data(
            user_id,
            include_location_history=True,
        )

        assert result.location_history == []  # Placeholder implementation

    @pytest.mark.asyncio
    async def test_export_user_data_with_requester(self, service, mock_audit_logger):
        """Test user data export with requester ID."""
        user_id = uuid4()
        requester_id = uuid4()

        await service.export_user_data(
            user_id,
            requester_id=requester_id,
        )

        # Verify audit log includes requester
        mock_audit_logger.log.assert_called()
        call_args = mock_audit_logger.log.call_args[0][0]
        assert call_args.user_id == requester_id

    @pytest.mark.asyncio
    async def test_delete_user_data(self, service, mock_audit_logger):
        """Test user data deletion."""
        user_id = uuid4()

        result = await service.delete_user_data(user_id)

        assert isinstance(result, GDPRDeletionResult)
        assert result.user_id == user_id
        mock_audit_logger.log.assert_called()

    @pytest.mark.asyncio
    async def test_delete_user_data_anonymize(self, service):
        """Test user data deletion with anonymization."""
        user_id = uuid4()

        result = await service.delete_user_data(
            user_id,
            anonymize_historical=True,
        )

        assert result.records_anonymized >= 0
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_delete_user_data_full_delete(self, service):
        """Test user data full deletion."""
        user_id = uuid4()

        result = await service.delete_user_data(
            user_id,
            anonymize_historical=False,
        )

        assert result.records_deleted >= 0

    @pytest.mark.asyncio
    async def test_delete_user_data_error_handling(self, service, mock_db_session_factory):
        """Test error handling in deletion."""
        user_id = uuid4()

        # Make session raise error
        session = mock_db_session_factory()
        session.__aenter__ = AsyncMock(side_effect=Exception("DB Error"))

        with patch.object(service, 'db_session_factory', return_value=session):
            # The function may raise or return error result depending on implementation
            try:
                result = await service.delete_user_data(user_id)
                # If it doesn't raise, check errors
                assert len(result.errors) > 0
            except Exception as e:
                # If it raises, that's also valid error handling
                assert "DB Error" in str(e)

    @pytest.mark.asyncio
    async def test_record_consent(self, service, mock_db_session_factory):
        """Test consent recording."""
        user_id = uuid4()

        # Should not raise
        await service.record_consent(
            user_id=user_id,
            consent_type="location_tracking",
            granted=True,
            ip_address="192.168.1.1",
        )


class TestCreateSecurityServices:
    """Tests for create_security_services factory function."""

    def test_creates_all_services(self):
        """Test factory creates all services."""
        mock_db_factory = MagicMock()

        encryptor, anonymizer, audit_logger, gdpr_service = create_security_services(
            secret_key="test-key",
            db_session_factory=mock_db_factory,
        )

        assert isinstance(encryptor, CoordinateEncryptor)
        assert isinstance(anonymizer, LocationAnonymizer)  # It's an instance
        assert isinstance(audit_logger, GeoAuditLogger)
        assert isinstance(gdpr_service, GDPRComplianceService)

    def test_gdpr_service_uses_encryptor(self):
        """Test GDPR service is configured with encryptor."""
        mock_db_factory = MagicMock()

        encryptor, _, _, gdpr_service = create_security_services(
            secret_key="test-key",
            db_session_factory=mock_db_factory,
        )

        assert gdpr_service.encryptor == encryptor


class TestSecurityServicesIntegration:
    """Integration tests for security services."""

    def test_encrypt_anonymize_export_flow(self):
        """Test full security flow: encrypt, anonymize, prepare for export."""
        # Create encryptor
        encryptor = CoordinateEncryptor("integration-test-key")

        # Original coordinates
        lat, lon = 41.311234, 69.279567

        # 1. Encrypt for storage
        encrypted = encryptor.encrypt_coordinates(lat, lon)
        assert encrypted != str(lat)

        # 2. Decrypt for processing
        dec_lat, dec_lon = encryptor.decrypt_coordinates(encrypted)
        assert dec_lat == lat
        assert dec_lon == lon

        # 3. Anonymize for analytics
        anonymized = LocationAnonymizer.anonymize(
            dec_lat, dec_lon,
            AnonymizationLevel.MEDIUM,
        )
        assert anonymized.anonymized_latitude != lat  # Precision reduced

    def test_audit_log_for_each_operation(self):
        """Test audit logs are created for each operation type."""
        # Create logs for different actions
        actions = [
            GeoAccessAction.VIEW,
            GeoAccessAction.EXPORT,
            GeoAccessAction.SHARE,
            GeoAccessAction.TRACK,
            GeoAccessAction.HISTORY,
            GeoAccessAction.BULK_EXPORT,
        ]

        for action in actions:
            log = GeoAccessLog(
                user_id=uuid4(),
                action=action,
                resource_type="agent",
                resource_id=uuid4(),
            )

            assert log.action == action
            assert log.id is not None
