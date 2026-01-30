"""
Security sub-package.

Contains security services for geolocation data:
- Encryption at rest for coordinates
- Location anonymization for analytics
- Audit logging for geo data access
- GDPR compliance (export, deletion)
"""
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

__all__ = [
    # Encryption
    "CoordinateEncryptor",
    # Anonymization
    "AnonymizationLevel",
    "AnonymizedLocation",
    "LocationAnonymizer",
    # Audit
    "GeoAccessAction",
    "GeoAccessLog",
    "GeoAuditLogger",
    # GDPR
    "GDPRExportResult",
    "GDPRDeletionResult",
    "GDPRComplianceService",
    # Factory
    "create_security_services",
]
