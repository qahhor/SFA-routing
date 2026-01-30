"""
Service for dispatching webhooks with HMAC-SHA256 signatures.

Security features:
- HMAC-SHA256 signature for payload verification
- Timestamp included to prevent replay attacks
- Retry logic with exponential backoff
- Delivery logging for audit trail
"""
import asyncio
import hmac
import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.webhook import WebhookSubscription

logger = logging.getLogger(__name__)


class WebhookDeliveryResult:
    """Result of a webhook delivery attempt."""

    def __init__(
        self,
        subscription_id: str,
        url: str,
        success: bool,
        status_code: Optional[int] = None,
        error: Optional[str] = None,
        attempts: int = 1,
        duration_ms: float = 0,
    ):
        self.subscription_id = subscription_id
        self.url = url
        self.success = success
        self.status_code = status_code
        self.error = error
        self.attempts = attempts
        self.duration_ms = duration_ms


class WebhookService:
    """
    Manages webhook dispatching with security and reliability features.

    Features:
    - HMAC-SHA256 signatures with timestamp (prevents replay attacks)
    - Retry logic with exponential backoff (3 attempts: 1s, 2s, 4s)
    - Comprehensive logging for debugging and audit
    - Async concurrent delivery for multiple subscriptions
    """

    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 2, 4]  # Exponential backoff in seconds
    TIMEOUT_SECONDS = 10.0

    @staticmethod
    def generate_signature(
        secret: str,
        payload: str,
        timestamp: int,
    ) -> str:
        """
        Generate HMAC-SHA256 signature.

        The signature is computed over: timestamp.payload
        This prevents replay attacks as timestamp must be recent.

        Args:
            secret: The webhook secret key
            payload: JSON payload string
            timestamp: Unix timestamp (seconds)

        Returns:
            Hex-encoded HMAC-SHA256 signature
        """
        message = f"{timestamp}.{payload}"
        return hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    @staticmethod
    def verify_signature(
        secret: str,
        payload: str,
        timestamp: int,
        signature: str,
        tolerance_seconds: int = 300,  # 5 minutes
    ) -> bool:
        """
        Verify webhook signature from incoming request.

        Args:
            secret: The webhook secret key
            payload: Raw request body
            timestamp: Timestamp from X-Webhook-Timestamp header
            signature: Signature from X-Webhook-Signature header
            tolerance_seconds: Max age of request in seconds

        Returns:
            True if signature is valid and timestamp is recent
        """
        # Check timestamp is recent (prevent replay attacks)
        now = int(time.time())
        if abs(now - timestamp) > tolerance_seconds:
            logger.warning(f"Webhook timestamp too old: {timestamp}, now: {now}")
            return False

        # Compute expected signature
        expected = WebhookService.generate_signature(secret, payload, timestamp)

        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected, signature)

    async def dispatch_event(
        self,
        db: AsyncSession,
        event_type: str,
        data: Dict[str, Any],
        idempotency_key: Optional[str] = None,
    ) -> List[WebhookDeliveryResult]:
        """
        Dispatch event to all subscribed webhooks.

        Args:
            db: Database session
            event_type: Event type (e.g., "optimization.completed")
            data: Event payload data
            idempotency_key: Optional key to prevent duplicate processing

        Returns:
            List of delivery results for each subscription
        """
        # Find active subscriptions for this event
        query = select(WebhookSubscription).where(
            WebhookSubscription.is_active.is_(True)
        )
        result = await db.execute(query)
        subs = result.scalars().all()

        # Filter subscriptions that want this event
        target_subs = [s for s in subs if event_type in (s.events or [])]

        if not target_subs:
            logger.debug(f"No webhooks subscribed to event: {event_type}")
            return []

        # Build payload with metadata
        timestamp = int(time.time())
        delivery_id = idempotency_key or str(uuid4())

        payload = {
            "id": delivery_id,
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": data,
        }
        payload_json = json.dumps(payload, default=str)

        # Dispatch to all subscriptions concurrently
        tasks = [
            self._deliver_to_subscription(sub, payload_json, timestamp, event_type)
            for sub in target_subs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        delivery_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                delivery_results.append(WebhookDeliveryResult(
                    subscription_id=str(target_subs[i].id),
                    url=target_subs[i].url,
                    success=False,
                    error=str(result),
                ))
            else:
                delivery_results.append(result)

        # Log summary
        success_count = sum(1 for r in delivery_results if r.success)
        logger.info(
            f"Webhook dispatch: event={event_type}, "
            f"total={len(delivery_results)}, success={success_count}"
        )

        return delivery_results

    async def _deliver_to_subscription(
        self,
        sub: WebhookSubscription,
        payload_json: str,
        timestamp: int,
        event_type: str,
    ) -> WebhookDeliveryResult:
        """
        Deliver webhook to a single subscription with retry logic.
        """
        # Use subscription secret or fall back to global secret
        secret = sub.secret or settings.WEBHOOK_SECRET_KEY
        if not secret:
            logger.warning(f"No secret configured for webhook {sub.id}")
            secret = "no-secret"  # Signature will be sent but may not verify

        signature = self.generate_signature(secret, payload_json, timestamp)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-ID": str(sub.id),
            "X-Webhook-Event": event_type,
            "X-Webhook-Timestamp": str(timestamp),
            "X-Webhook-Signature": f"sha256={signature}",
            "User-Agent": "SFA-Routing-Webhook/1.0",
        }

        start_time = time.time()
        last_error = None
        attempts = 0

        async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
            for attempt in range(self.MAX_RETRIES):
                attempts = attempt + 1
                try:
                    response = await client.post(
                        sub.url,
                        content=payload_json,
                        headers=headers,
                    )

                    duration_ms = (time.time() - start_time) * 1000

                    if response.status_code < 400:
                        logger.debug(
                            f"Webhook delivered: url={sub.url}, "
                            f"status={response.status_code}, "
                            f"attempts={attempts}"
                        )
                        return WebhookDeliveryResult(
                            subscription_id=str(sub.id),
                            url=sub.url,
                            success=True,
                            status_code=response.status_code,
                            attempts=attempts,
                            duration_ms=duration_ms,
                        )
                    else:
                        last_error = f"HTTP {response.status_code}"
                        logger.warning(
                            f"Webhook failed: url={sub.url}, "
                            f"status={response.status_code}, "
                            f"attempt={attempts}/{self.MAX_RETRIES}"
                        )

                except httpx.TimeoutException:
                    last_error = "Timeout"
                    logger.warning(
                        f"Webhook timeout: url={sub.url}, "
                        f"attempt={attempts}/{self.MAX_RETRIES}"
                    )

                except httpx.RequestError as e:
                    last_error = str(e)
                    logger.warning(
                        f"Webhook request error: url={sub.url}, "
                        f"error={e}, attempt={attempts}/{self.MAX_RETRIES}"
                    )

                # Wait before retry (except on last attempt)
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAYS[attempt])

        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Webhook delivery failed after {attempts} attempts: "
            f"url={sub.url}, error={last_error}"
        )

        return WebhookDeliveryResult(
            subscription_id=str(sub.id),
            url=sub.url,
            success=False,
            error=last_error,
            attempts=attempts,
            duration_ms=duration_ms,
        )


# Singleton instance
webhook_service = WebhookService()
