"""
Service for dispatching webhooks.
"""
import hmac
import hashlib
import json
import httpx
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import WebhookSubscription


class WebhookService:
    """
    Manages webhook dispatching.
    """
    
    @staticmethod
    def _generate_signature(secret: str, payload: str) -> str:
        """Generate HMAC SHA256 signature."""
        return hmac.new(
            secret.encode(), 
            payload.encode(), 
            hashlib.sha256
        ).hexdigest()

    async def dispatch_event(
        self,
        db: AsyncSession,
        event_type: str,
        data: Dict[str, Any]
    ):
        """
        Dispatch event to all subscribed webhooks.
        """
        # Find active subscriptions for this event
        # Postgres array contains:  events @> ARRAY[event_type]
        # Or simplistic filtering in app if simple list
        
        # AsyncQuery
        query = select(WebhookSubscription).where(
            WebhookSubscription.is_active == True
        )
        result = await db.execute(query)
        subs = result.scalars().all()
        
        # Filter in memory for compatibility/simplicity
        target_subs = [s for s in subs if event_type in s.events]
        
        if not target_subs:
            return

        payload = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        payload_json = json.dumps(payload)

        async with httpx.AsyncClient(timeout=5.0) as client:
            for sub in target_subs:
                signature = self._generate_signature(sub.secret, payload_json)
                headers = {
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                    "X-Webhook-Event": event_type
                }
                
                try:
                    await client.post(
                        sub.url,
                        content=payload_json,
                        headers=headers
                    )
                    # TODO: Log successful delivery
                except Exception as e:
                    print(f"Failed to send webhook to {sub.url}: {e}")
                    # TODO: Retry logic?

webhook_service = WebhookService()
