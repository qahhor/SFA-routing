"""
Predictive Rerouting Engine (R7).

Provides proactive route optimization by:
- Predicting delays before they occur
- Checking schedule feasibility periodically
- Triggering re-optimization proactively

Unlike reactive rerouting (which waits for GPS deviation),
predictive rerouting anticipates problems and acts before
they impact customer service.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import Agent
from app.models.visit_plan import VisitPlan
from app.services.analytics import ETACalibrationService, TrafficAwareETA
from app.services.planning.rerouting import RerouteResult, rerouting_service
from app.services.realtime.websocket_manager import manager

logger = logging.getLogger(__name__)


@dataclass
class ScheduleFeasibilityCheck:
    """Result of schedule feasibility analysis."""

    agent_id: UUID
    check_time: datetime
    is_feasible: bool
    at_risk_visits: list[UUID] = field(default_factory=list)
    predicted_delays: dict[UUID, int] = field(default_factory=dict)  # visit_id -> delay_minutes
    recommendations: list[str] = field(default_factory=list)
    total_predicted_delay_minutes: int = 0


@dataclass
class PredictiveAlert:
    """Alert for predicted schedule issue."""

    alert_id: str
    agent_id: UUID
    severity: str  # "warning", "critical"
    message: str
    affected_visits: list[UUID]
    predicted_delay_minutes: int
    recommendation: str
    created_at: datetime = field(default_factory=datetime.utcnow)


class PredictiveReroutingEngine:
    """
    Engine for proactive route optimization.

    Key Features:
    1. Periodic feasibility checks (every 30 min)
    2. Delay prediction based on current progress
    3. Proactive re-optimization triggers
    4. Alert generation for dispatchers

    Usage:
        engine = PredictiveReroutingEngine()

        # Manual check
        result = await engine.check_schedule_feasibility(db, agent_id)

        # Continuous monitoring (run in background)
        await engine.start_monitoring(db, check_interval_minutes=30)
    """

    # Configuration
    CHECK_INTERVAL_MINUTES = 30
    DELAY_WARNING_THRESHOLD_MINUTES = 15
    DELAY_CRITICAL_THRESHOLD_MINUTES = 30
    PROACTIVE_REROUTE_THRESHOLD_MINUTES = 20

    # Buffer for time window calculations
    TIME_WINDOW_BUFFER_MINUTES = 10

    def __init__(self, region: str = "default"):
        self.region = region
        self._running = False
        self._alerts: dict[str, PredictiveAlert] = {}
        self.eta_calibration = ETACalibrationService()

    async def check_schedule_feasibility(
        self,
        db: AsyncSession,
        agent_id: UUID,
        current_time: Optional[datetime] = None,
        current_location: Optional[tuple[float, float]] = None,
    ) -> ScheduleFeasibilityCheck:
        """
        Check if agent's remaining schedule is feasible.

        Analyzes:
        - Current progress vs. plan
        - Traffic conditions for remaining route
        - Time window compliance
        - Total workday constraints

        Returns:
            ScheduleFeasibilityCheck with detailed analysis
        """
        if current_time is None:
            current_time = datetime.now()

        today = current_time.date()

        # Get remaining visits
        result = await db.execute(
            select(VisitPlan)
            .where(
                and_(
                    VisitPlan.agent_id == agent_id,
                    VisitPlan.planned_date == today,
                    VisitPlan.status == "planned",
                )
            )
            .options(selectinload(VisitPlan.client))
            .order_by(VisitPlan.sequence_number)
        )
        remaining_visits = result.scalars().all()

        # Get agent for work end time
        agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = agent_result.scalar_one_or_none()

        if not remaining_visits:
            return ScheduleFeasibilityCheck(
                agent_id=agent_id,
                check_time=current_time,
                is_feasible=True,
            )

        # Analyze each remaining visit
        at_risk_visits = []
        predicted_delays = {}
        recommendations = []
        total_delay = 0

        # Start from current location or first visit
        if current_location:
            current_lat, current_lon = current_location
        else:
            first_client = remaining_visits[0].client
            if first_client:
                current_lat = float(first_client.latitude)
                current_lon = float(first_client.longitude)
            else:
                current_lat, current_lon = 0.0, 0.0

        simulated_time = current_time

        for i, visit in enumerate(remaining_visits):
            if not visit.client:
                continue

            client = visit.client

            # Estimate travel time to this visit
            if i > 0:
                prev_client = remaining_visits[i - 1].client
                if prev_client:
                    travel_seconds = await self._estimate_travel_time(
                        float(prev_client.latitude),
                        float(prev_client.longitude),
                        float(client.latitude),
                        float(client.longitude),
                        simulated_time,
                    )
                else:
                    travel_seconds = 900  # Default 15 min
            else:
                # Travel from current location
                travel_seconds = await self._estimate_travel_time(
                    current_lat,
                    current_lon,
                    float(client.latitude),
                    float(client.longitude),
                    simulated_time,
                )

            # Predicted arrival
            predicted_arrival = simulated_time + timedelta(seconds=travel_seconds)

            # Check against time window
            time_window_end = datetime.combine(today, client.time_window_end)

            if predicted_arrival > time_window_end:
                delay_minutes = int((predicted_arrival - time_window_end).total_seconds() / 60)
                at_risk_visits.append(visit.id)
                predicted_delays[visit.id] = delay_minutes
                total_delay += delay_minutes

            elif predicted_arrival > time_window_end - timedelta(minutes=self.TIME_WINDOW_BUFFER_MINUTES):
                # Within buffer - at risk
                at_risk_visits.append(visit.id)
                predicted_delays[visit.id] = 0  # Not late yet, but at risk

            # Update simulated time (arrival + service)
            service_minutes = client.visit_duration_minutes or 15
            simulated_time = predicted_arrival + timedelta(minutes=service_minutes)

        # Check work end time
        if agent and agent.work_end:
            work_end = datetime.combine(today, agent.work_end)
            if simulated_time > work_end:
                overtime_minutes = int((simulated_time - work_end).total_seconds() / 60)
                recommendations.append(
                    f"Schedule extends {overtime_minutes} min past work end time. "
                    "Consider reassigning last visits or extending hours."
                )

        # Generate recommendations
        if at_risk_visits:
            if total_delay > self.PROACTIVE_REROUTE_THRESHOLD_MINUTES:
                recommendations.append(
                    f"Proactive re-optimization recommended. " f"Predicted total delay: {total_delay} minutes."
                )
            else:
                recommendations.append(
                    f"{len(at_risk_visits)} visits at risk of delay. " "Monitor closely and prepare contingency."
                )

        is_feasible = total_delay < self.DELAY_WARNING_THRESHOLD_MINUTES

        return ScheduleFeasibilityCheck(
            agent_id=agent_id,
            check_time=current_time,
            is_feasible=is_feasible,
            at_risk_visits=at_risk_visits,
            predicted_delays=predicted_delays,
            recommendations=recommendations,
            total_predicted_delay_minutes=total_delay,
        )

    async def check_and_trigger_proactive_reroute(
        self,
        db: AsyncSession,
        agent_id: UUID,
        current_location: Optional[tuple[float, float]] = None,
    ) -> Optional[RerouteResult]:
        """
        Check feasibility and trigger re-optimization if needed.

        Combines feasibility check with automatic re-routing
        when thresholds are exceeded.

        Returns:
            RerouteResult if re-optimization was triggered, None otherwise
        """
        feasibility = await self.check_schedule_feasibility(db, agent_id, current_location=current_location)

        # Create alert if needed
        if feasibility.total_predicted_delay_minutes >= self.DELAY_WARNING_THRESHOLD_MINUTES:
            severity = (
                "critical"
                if feasibility.total_predicted_delay_minutes >= self.DELAY_CRITICAL_THRESHOLD_MINUTES
                else "warning"
            )

            alert = PredictiveAlert(
                alert_id=f"{agent_id}_{datetime.utcnow().timestamp()}",
                agent_id=agent_id,
                severity=severity,
                message=f"Predicted delay of {feasibility.total_predicted_delay_minutes} minutes",
                affected_visits=feasibility.at_risk_visits,
                predicted_delay_minutes=feasibility.total_predicted_delay_minutes,
                recommendation=feasibility.recommendations[0] if feasibility.recommendations else "",
            )
            self._alerts[alert.alert_id] = alert

            # Broadcast alert
            await self._broadcast_alert(alert)

        # Trigger re-optimization if threshold exceeded
        if feasibility.total_predicted_delay_minutes >= self.PROACTIVE_REROUTE_THRESHOLD_MINUTES:
            logger.info(
                f"Triggering proactive re-optimization for agent {agent_id}: "
                f"predicted delay {feasibility.total_predicted_delay_minutes} min"
            )

            if current_location:
                current_lat, current_lon = current_location
            else:
                # Get agent's current GPS if available
                agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
                agent = agent_result.scalar_one_or_none()
                if agent and agent.current_latitude and agent.current_longitude:
                    current_lat = float(agent.current_latitude)
                    current_lon = float(agent.current_longitude)
                else:
                    # Can't reroute without location
                    return None

            return await rerouting_service.reroute_agent_visits(
                db=db,
                agent_id=agent_id,
                current_lat=current_lat,
                current_lon=current_lon,
                reason="proactive_optimization",
            )

        return None

    async def monitor_all_agents(
        self,
        db: AsyncSession,
    ) -> list[ScheduleFeasibilityCheck]:
        """
        Check schedule feasibility for all active agents.

        Used for periodic monitoring.
        """
        today = datetime.now().date()

        # Get agents with visits today
        result = await db.execute(select(Agent).where(Agent.is_active.is_(True)).options(selectinload(Agent.visit_plans)))
        agents = result.scalars().all()

        checks = []
        for agent in agents:
            # Only check agents with remaining work
            has_remaining = any(vp.planned_date == today and vp.status == "planned" for vp in agent.visit_plans)
            if not has_remaining:
                continue

            try:
                check = await self.check_schedule_feasibility(db, agent.id)
                checks.append(check)
            except Exception as e:
                logger.error(f"Failed to check agent {agent.id}: {e}")

        return checks

    async def get_fleet_status(
        self,
        db: AsyncSession,
    ) -> dict:
        """
        Get overall fleet status with risk summary.

        Returns dict with:
        - total_agents: Number of active agents
        - on_track: Agents with feasible schedules
        - at_risk: Agents with minor delays predicted
        - critical: Agents with major delays predicted
        - total_predicted_delay: Sum of all predicted delays
        """
        checks = await self.monitor_all_agents(db)

        on_track = 0
        at_risk = 0
        critical = 0
        total_delay = 0

        for check in checks:
            total_delay += check.total_predicted_delay_minutes

            if check.is_feasible:
                on_track += 1
            elif check.total_predicted_delay_minutes >= self.DELAY_CRITICAL_THRESHOLD_MINUTES:
                critical += 1
            else:
                at_risk += 1

        return {
            "total_agents": len(checks),
            "on_track": on_track,
            "at_risk": at_risk,
            "critical": critical,
            "total_predicted_delay_minutes": total_delay,
            "checks": checks,
        }

    async def start_monitoring(
        self,
        db_session_factory,
        check_interval_minutes: int = None,
    ):
        """
        Start continuous monitoring loop.

        Should be run as a background task.
        """
        if check_interval_minutes is None:
            check_interval_minutes = self.CHECK_INTERVAL_MINUTES

        self._running = True
        logger.info(f"Starting predictive monitoring, interval: {check_interval_minutes} min")

        while self._running:
            try:
                async with db_session_factory() as db:
                    checks = await self.monitor_all_agents(db)

                    # Log summary
                    at_risk_count = sum(1 for c in checks if not c.is_feasible)
                    if at_risk_count > 0:
                        logger.warning(f"Monitoring: {at_risk_count}/{len(checks)} agents at risk")

                    # Trigger proactive re-routes where needed
                    for check in checks:
                        if check.total_predicted_delay_minutes >= self.PROACTIVE_REROUTE_THRESHOLD_MINUTES:
                            await self.check_and_trigger_proactive_reroute(db, check.agent_id)

            except Exception as e:
                logger.error(f"Monitoring cycle failed: {e}")

            await asyncio.sleep(check_interval_minutes * 60)

    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self._running = False

    async def _estimate_travel_time(
        self,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float,
        departure_time: datetime,
    ) -> int:
        """
        Estimate travel time considering traffic.

        Returns seconds.
        """
        from app.services.routing.osrm_client import osrm_client

        try:
            # Get base OSRM estimate
            result = await osrm_client.get_route([(from_lon, from_lat), (to_lon, to_lat)])
            base_seconds = result.duration_seconds

            # Apply traffic adjustment
            adjusted = TrafficAwareETA.adjust_duration(
                base_seconds,
                departure_time.time(),
                self.region,
            )

            # Apply learned calibration
            calibrated = self.eta_calibration.calibrate_duration(
                adjusted,
                departure_time,
                self.region,
            )

            return calibrated

        except Exception as e:
            logger.warning(f"Travel time estimation failed, using fallback: {e}")
            # Fallback: estimate based on straight-line distance
            import math

            R = 6371000  # Earth radius
            dlat = math.radians(to_lat - from_lat)
            dlon = math.radians(to_lon - from_lon)
            a = (
                math.sin(dlat / 2) ** 2
                + math.cos(math.radians(from_lat)) * math.cos(math.radians(to_lat)) * math.sin(dlon / 2) ** 2
            )
            distance = R * 2 * math.asin(math.sqrt(a))

            # Assume 30 km/h average with traffic multiplier
            base_seconds = distance / 8.33  # 30 km/h = 8.33 m/s
            return int(
                TrafficAwareETA.adjust_duration(
                    int(base_seconds),
                    departure_time.time(),
                    self.region,
                )
            )

    async def _broadcast_alert(self, alert: PredictiveAlert):
        """Broadcast predictive alert to dispatchers."""
        await manager.broadcast(
            {
                "type": "predictive_alert",
                "alert_id": alert.alert_id,
                "agent_id": str(alert.agent_id),
                "severity": alert.severity,
                "message": alert.message,
                "affected_visits": [str(v) for v in alert.affected_visits],
                "predicted_delay_minutes": alert.predicted_delay_minutes,
                "recommendation": alert.recommendation,
                "created_at": alert.created_at.isoformat(),
            },
            topic="dispatchers",
        )


# Singleton instance
predictive_engine = PredictiveReroutingEngine()
