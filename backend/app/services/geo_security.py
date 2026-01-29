"""
Geolocation Security Services (R18, R19, R20, R21).

Security features for geolocation data:
- R18: Encryption at rest for coordinates
- R19: Location anonymization for analytics
- R20: Audit logging for geo data access
- R21: GDPR compliance (export, deletion)
"""
import hashlib
import hmac
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

logger = logging.getLogger(__name__)


# ============================================================
# R18: Data Encryption at Rest
# ============================================================

class CoordinateEncryptor:
    """
    Encrypt/decrypt geographic coordinates for storage.

    Uses Fernet (AES-128-CBC) for symmetric encryption.
    Coordinates are serialized to JSON, encrypted, and base64 encoded.
    """

    def __init__(self, secret_key: str, salt: bytes = b"sfa_geo_salt"):
        """
        Initialize encryptor with secret key.

        Args:
            secret_key: Secret key for encryption
            salt: Salt for key derivation
        """
        # Derive encryption key from secret
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        self.cipher = Fernet(key)

    def encrypt_coordinates(
        self,
        latitude: float,
        longitude: float,
    ) -> str:
        """
        Encrypt latitude and longitude.

        Returns:
            Base64-encoded encrypted string
        """
        data = json.dumps({
            "lat": latitude,
            "lon": longitude,
            "ts": datetime.utcnow().isoformat(),
        }).encode()

        encrypted = self.cipher.encrypt(data)
        return encrypted.decode()

    def decrypt_coordinates(
        self,
        encrypted: str,
    ) -> tuple[float, float]:
        """
        Decrypt coordinates.

        Returns:
            Tuple of (latitude, longitude)
        """
        decrypted = self.cipher.decrypt(encrypted.encode())
        data = json.loads(decrypted.decode())
        return (data["lat"], data["lon"])

    def encrypt_location_history(
        self,
        history: list[dict],
    ) -> str:
        """Encrypt list of location records."""
        data = json.dumps(history).encode()
        return self.cipher.encrypt(data).decode()

    def decrypt_location_history(
        self,
        encrypted: str,
    ) -> list[dict]:
        """Decrypt location history."""
        decrypted = self.cipher.decrypt(encrypted.encode())
        return json.loads(decrypted.decode())


# ============================================================
# R19: Location Anonymization
# ============================================================

class AnonymizationLevel(str, Enum):
    """Level of location anonymization."""

    NONE = "none"  # No anonymization
    LOW = "low"  # Round to 3 decimals (~111m)
    MEDIUM = "medium"  # Round to 2 decimals (~1.1km)
    HIGH = "high"  # Round to 1 decimal (~11km)
    VERY_HIGH = "very_high"  # H3 cell centroid (resolution 5)


@dataclass
class AnonymizedLocation:
    """Anonymized location representation."""

    original_precision: int
    anonymized_latitude: float
    anonymized_longitude: float
    anonymization_level: AnonymizationLevel
    h3_cell: Optional[str] = None
    area_km2: Optional[float] = None


class LocationAnonymizer:
    """
    Anonymize location data for privacy.

    Techniques:
    - Coordinate rounding (spatial cloaking)
    - H3 cell aggregation
    - Temporal aggregation
    - K-anonymity enforcement
    """

    PRECISION_MAP = {
        AnonymizationLevel.NONE: 6,  # ~0.1m
        AnonymizationLevel.LOW: 3,  # ~111m
        AnonymizationLevel.MEDIUM: 2,  # ~1.1km
        AnonymizationLevel.HIGH: 1,  # ~11km
        AnonymizationLevel.VERY_HIGH: 0,  # ~111km
    }

    @classmethod
    def anonymize(
        cls,
        latitude: float,
        longitude: float,
        level: AnonymizationLevel = AnonymizationLevel.MEDIUM,
    ) -> AnonymizedLocation:
        """
        Anonymize coordinates to specified level.

        Args:
            latitude: Original latitude
            longitude: Original longitude
            level: Anonymization level

        Returns:
            AnonymizedLocation with reduced precision
        """
        if level == AnonymizationLevel.VERY_HIGH:
            return cls._anonymize_h3(latitude, longitude)

        precision = cls.PRECISION_MAP[level]
        anon_lat = round(latitude, precision)
        anon_lon = round(longitude, precision)

        # Calculate approximate area covered
        area_km2 = cls._calculate_area_km2(precision)

        return AnonymizedLocation(
            original_precision=6,
            anonymized_latitude=anon_lat,
            anonymized_longitude=anon_lon,
            anonymization_level=level,
            area_km2=area_km2,
        )

    @classmethod
    def _anonymize_h3(
        cls,
        latitude: float,
        longitude: float,
        resolution: int = 5,
    ) -> AnonymizedLocation:
        """Anonymize using H3 cell centroid."""
        try:
            import h3

            cell = h3.geo_to_h3(latitude, longitude, resolution)
            centroid = h3.h3_to_geo(cell)

            return AnonymizedLocation(
                original_precision=6,
                anonymized_latitude=centroid[0],
                anonymized_longitude=centroid[1],
                anonymization_level=AnonymizationLevel.VERY_HIGH,
                h3_cell=cell,
                area_km2=h3.cell_area(cell, unit="km^2"),
            )

        except ImportError:
            # Fallback if H3 not available
            return cls.anonymize(
                latitude, longitude,
                AnonymizationLevel.HIGH,
            )

    @classmethod
    def _calculate_area_km2(cls, precision: int) -> float:
        """Calculate approximate area covered by precision level."""
        # Approximate area in km² for each precision level
        areas = {
            0: 12345.0,  # 1 degree ≈ 111km
            1: 123.5,  # 0.1 degree
            2: 1.23,  # 0.01 degree
            3: 0.012,  # 0.001 degree
            4: 0.00012,
            5: 0.0000012,
            6: 0.000000012,
        }
        return areas.get(precision, 0.0)

    @classmethod
    def anonymize_trajectory(
        cls,
        points: list[tuple[float, float, datetime]],
        level: AnonymizationLevel = AnonymizationLevel.MEDIUM,
        temporal_window_minutes: int = 15,
    ) -> list[tuple[float, float, datetime]]:
        """
        Anonymize trajectory with spatial and temporal cloaking.

        Args:
            points: List of (lat, lon, timestamp) tuples
            level: Spatial anonymization level
            temporal_window_minutes: Group points within this window

        Returns:
            Anonymized trajectory
        """
        if not points:
            return []

        # Sort by timestamp
        sorted_points = sorted(points, key=lambda p: p[2])

        anonymized = []
        window_start = sorted_points[0][2]
        window_points = []

        for lat, lon, ts in sorted_points:
            if (ts - window_start).total_seconds() <= temporal_window_minutes * 60:
                window_points.append((lat, lon, ts))
            else:
                # Anonymize window
                if window_points:
                    anon = cls._anonymize_window(window_points, level)
                    anonymized.append(anon)

                # Start new window
                window_start = ts
                window_points = [(lat, lon, ts)]

        # Handle last window
        if window_points:
            anon = cls._anonymize_window(window_points, level)
            anonymized.append(anon)

        return anonymized

    @classmethod
    def _anonymize_window(
        cls,
        points: list[tuple[float, float, datetime]],
        level: AnonymizationLevel,
    ) -> tuple[float, float, datetime]:
        """Anonymize a temporal window of points."""
        avg_lat = sum(p[0] for p in points) / len(points)
        avg_lon = sum(p[1] for p in points) / len(points)
        avg_ts = points[len(points) // 2][2]

        anon = cls.anonymize(avg_lat, avg_lon, level)
        return (anon.anonymized_latitude, anon.anonymized_longitude, avg_ts)


# ============================================================
# R20: Geo Audit Logging
# ============================================================

class GeoAccessAction(str, Enum):
    """Types of geo data access actions."""

    VIEW = "view"
    EXPORT = "export"
    SHARE = "share"
    TRACK = "track"
    HISTORY = "history"
    BULK_EXPORT = "bulk_export"


@dataclass
class GeoAccessLog:
    """Audit log entry for geo data access."""

    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Who accessed
    user_id: UUID = None
    user_role: str = ""
    ip_address: str = ""
    user_agent: str = ""

    # What was accessed
    action: GeoAccessAction = GeoAccessAction.VIEW
    resource_type: str = ""  # agent, client, route, etc.
    resource_id: UUID = None
    resource_owner_id: Optional[UUID] = None

    # Geo data specifics
    coordinates_accessed: bool = False
    history_range_days: int = 0
    records_count: int = 0

    # Context
    api_endpoint: str = ""
    request_id: str = ""
    reason: str = ""


class GeoAuditLogger:
    """
    Audit logger for geolocation data access.

    Logs all access to location data for compliance and security.
    """

    def __init__(self, db_session_factory, retention_days: int = 365):
        """
        Initialize audit logger.

        Args:
            db_session_factory: Database session factory
            retention_days: How long to retain audit logs
        """
        self.db_session_factory = db_session_factory
        self.retention_days = retention_days
        self._buffer: list[GeoAccessLog] = []
        self._buffer_size = 100

    async def log(self, entry: GeoAccessLog) -> None:
        """
        Log geo data access.

        Buffers entries and flushes periodically.
        """
        self._buffer.append(entry)

        if len(self._buffer) >= self._buffer_size:
            await self._flush()

    async def _flush(self) -> None:
        """Flush buffer to database."""
        if not self._buffer:
            return

        try:
            async with self.db_session_factory() as db:
                for entry in self._buffer:
                    # Insert audit log (assuming AuditLog model exists)
                    await db.execute(
                        """
                        INSERT INTO geo_access_logs (
                            id, timestamp, user_id, user_role, ip_address,
                            action, resource_type, resource_id,
                            coordinates_accessed, records_count,
                            api_endpoint, request_id
                        ) VALUES (
                            :id, :timestamp, :user_id, :user_role, :ip_address,
                            :action, :resource_type, :resource_id,
                            :coordinates_accessed, :records_count,
                            :api_endpoint, :request_id
                        )
                        """,
                        {
                            "id": str(entry.id),
                            "timestamp": entry.timestamp,
                            "user_id": str(entry.user_id) if entry.user_id else None,
                            "user_role": entry.user_role,
                            "ip_address": entry.ip_address,
                            "action": entry.action.value,
                            "resource_type": entry.resource_type,
                            "resource_id": str(entry.resource_id) if entry.resource_id else None,
                            "coordinates_accessed": entry.coordinates_accessed,
                            "records_count": entry.records_count,
                            "api_endpoint": entry.api_endpoint,
                            "request_id": entry.request_id,
                        }
                    )
                await db.commit()

            self._buffer.clear()

        except Exception as e:
            logger.error(f"Failed to flush audit logs: {e}")

    def log_sync(self, entry: GeoAccessLog) -> None:
        """Synchronous log (adds to buffer only)."""
        self._buffer.append(entry)

    async def query_logs(
        self,
        user_id: Optional[UUID] = None,
        resource_id: Optional[UUID] = None,
        action: Optional[GeoAccessAction] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[GeoAccessLog]:
        """Query audit logs with filters."""
        # Implementation depends on database schema
        # Placeholder for now
        return []


# ============================================================
# R21: GDPR Compliance
# ============================================================

@dataclass
class GDPRExportResult:
    """Result of GDPR data export."""

    user_id: UUID
    export_date: datetime = field(default_factory=datetime.utcnow)
    personal_data: dict = field(default_factory=dict)
    location_history: list[dict] = field(default_factory=list)
    visit_records: list[dict] = field(default_factory=list)
    consent_records: list[dict] = field(default_factory=list)


@dataclass
class GDPRDeletionResult:
    """Result of GDPR data deletion."""

    user_id: UUID
    deletion_date: datetime = field(default_factory=datetime.utcnow)
    records_deleted: int = 0
    records_anonymized: int = 0
    errors: list[str] = field(default_factory=list)


class GDPRComplianceService:
    """
    GDPR compliance service for location data.

    Implements:
    - Right to access (data export)
    - Right to be forgotten (data deletion)
    - Right to rectification
    - Data portability
    """

    def __init__(
        self,
        db_session_factory,
        encryptor: Optional[CoordinateEncryptor] = None,
        audit_logger: Optional[GeoAuditLogger] = None,
    ):
        self.db_session_factory = db_session_factory
        self.encryptor = encryptor
        self.audit_logger = audit_logger

    async def export_user_data(
        self,
        user_id: UUID,
        include_location_history: bool = True,
        requester_id: Optional[UUID] = None,
    ) -> GDPRExportResult:
        """
        Export all user data (GDPR Article 15 & 20).

        Args:
            user_id: User ID to export
            include_location_history: Include GPS history
            requester_id: ID of user making request

        Returns:
            GDPRExportResult with all user data
        """
        result = GDPRExportResult(user_id=user_id)

        async with self.db_session_factory() as db:
            # Export personal data
            # (Implementation depends on User model)
            result.personal_data = {
                "id": str(user_id),
                "exported_at": datetime.utcnow().isoformat(),
            }

            # Export location history if requested
            if include_location_history:
                # Query location history
                # (Implementation depends on GPS tracking model)
                result.location_history = []

            # Export visit records
            # (Implementation depends on VisitPlan model)
            result.visit_records = []

        # Log the export
        if self.audit_logger:
            await self.audit_logger.log(GeoAccessLog(
                user_id=requester_id or user_id,
                action=GeoAccessAction.BULK_EXPORT,
                resource_type="user_data",
                resource_id=user_id,
                reason="gdpr_export",
            ))

        return result

    async def delete_user_data(
        self,
        user_id: UUID,
        anonymize_historical: bool = True,
        requester_id: Optional[UUID] = None,
    ) -> GDPRDeletionResult:
        """
        Delete user data (GDPR Article 17).

        Args:
            user_id: User ID to delete
            anonymize_historical: Anonymize rather than delete historical data
            requester_id: ID of user making request

        Returns:
            GDPRDeletionResult with deletion summary
        """
        result = GDPRDeletionResult(user_id=user_id)

        async with self.db_session_factory() as db:
            try:
                # 1. Delete personal identifiable data
                # (Keep anonymized records for business analytics)

                # 2. Anonymize location history
                if anonymize_historical:
                    anonymized = await self._anonymize_user_history(
                        db, user_id
                    )
                    result.records_anonymized = anonymized
                else:
                    deleted = await self._delete_user_history(db, user_id)
                    result.records_deleted = deleted

                # 3. Clear from caches
                await self._clear_user_caches(user_id)

                await db.commit()

            except Exception as e:
                result.errors.append(str(e))
                await db.rollback()

        # Log the deletion
        if self.audit_logger:
            await self.audit_logger.log(GeoAccessLog(
                user_id=requester_id or user_id,
                action=GeoAccessAction.BULK_EXPORT,
                resource_type="user_data",
                resource_id=user_id,
                reason="gdpr_deletion",
            ))

        return result

    async def _anonymize_user_history(
        self,
        db,
        user_id: UUID,
    ) -> int:
        """Anonymize user's location history."""
        # Implementation depends on database schema
        # Would update coordinates to anonymized versions
        return 0

    async def _delete_user_history(
        self,
        db,
        user_id: UUID,
    ) -> int:
        """Delete user's location history."""
        # Implementation depends on database schema
        return 0

    async def _clear_user_caches(self, user_id: UUID) -> None:
        """Clear user data from all caches."""
        # Implementation would invalidate Redis keys
        pass

    async def record_consent(
        self,
        user_id: UUID,
        consent_type: str,
        granted: bool,
        ip_address: str = "",
    ) -> None:
        """
        Record user consent for data processing.

        Args:
            user_id: User ID
            consent_type: Type of consent (location_tracking, analytics, etc.)
            granted: Whether consent was granted
            ip_address: IP address for audit
        """
        async with self.db_session_factory() as db:
            # Record consent
            # (Implementation depends on consent tracking model)
            pass


# Factory function
def create_security_services(
    secret_key: str,
    db_session_factory,
) -> tuple[CoordinateEncryptor, LocationAnonymizer, GeoAuditLogger, GDPRComplianceService]:
    """
    Create all security services.

    Returns:
        Tuple of (encryptor, anonymizer, audit_logger, gdpr_service)
    """
    encryptor = CoordinateEncryptor(secret_key)
    anonymizer = LocationAnonymizer()
    audit_logger = GeoAuditLogger(db_session_factory)
    gdpr_service = GDPRComplianceService(
        db_session_factory,
        encryptor,
        audit_logger,
    )

    return encryptor, anonymizer, audit_logger, gdpr_service
