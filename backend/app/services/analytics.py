"""
Advanced Analytics Service for SFA-Routing.

Implements strategic recommendations:
- R1: Dynamic service time calculation
- R3: Skill-based agent-client assignment
- R4: Predictive visit frequency
- R5: Traffic multipliers by time of day
- R6: ETA calibration
- R8: Smart priority refresh
- R10: Visit outcome feedback
- R11: Customer satisfaction scoring
"""
import enum
import math
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession


# ============================================================================
# R1: Dynamic Service Time Calculation
# ============================================================================

class ServiceTimeCalculator:
    """
    Calculate dynamic visit duration based on client characteristics.

    Replaces fixed 15-minute service time with intelligent calculation
    considering client category, expected order size, and historical data.
    """

    # Base times by category (minutes)
    BASE_TIMES = {
        "A": 25,  # Key accounts need more attention
        "B": 15,  # Standard visits
        "C": 10,  # Quick check-ins
    }

    # Multipliers for various conditions
    MULTIPLIERS = {
        "new_client": 1.5,        # New clients need onboarding
        "has_promo": 1.2,         # Promo explanation takes time
        "high_debt": 1.3,         # Debt discussion needed
        "large_order": 1.25,      # More SKUs to process
        "first_visit_week": 1.1,  # First weekly visit is longer
    }

    # SKU-based additions (minutes per 10 SKUs)
    SKU_TIME_PER_10 = 3

    @classmethod
    def calculate(
        cls,
        category: str,
        expected_sku_count: int = 0,
        is_new_client: bool = False,
        has_active_promo: bool = False,
        outstanding_debt: float = 0,
        is_first_visit_of_week: bool = True,
        historical_avg_minutes: Optional[float] = None,
    ) -> int:
        """
        Calculate dynamic service time in minutes.

        Args:
            category: Client category (A, B, C)
            expected_sku_count: Expected number of SKUs in order
            is_new_client: Whether client is new (<30 days)
            has_active_promo: Whether client has active promotion
            outstanding_debt: Outstanding debt amount
            is_first_visit_of_week: Whether this is first visit this week
            historical_avg_minutes: Historical average visit duration

        Returns:
            Estimated service time in minutes
        """
        # Start with base time
        base = cls.BASE_TIMES.get(category.upper(), 15)

        # Apply multipliers
        multiplier = 1.0

        if is_new_client:
            multiplier *= cls.MULTIPLIERS["new_client"]

        if has_active_promo:
            multiplier *= cls.MULTIPLIERS["has_promo"]

        if outstanding_debt > 1000:  # Significant debt threshold
            multiplier *= cls.MULTIPLIERS["high_debt"]

        if expected_sku_count > 20:
            multiplier *= cls.MULTIPLIERS["large_order"]

        if is_first_visit_of_week and category.upper() == "A":
            multiplier *= cls.MULTIPLIERS["first_visit_week"]

        # Add SKU-based time
        sku_time = (expected_sku_count // 10) * cls.SKU_TIME_PER_10

        # Calculate raw estimate
        estimated = base * multiplier + sku_time

        # Blend with historical data if available (70% calculated, 30% historical)
        if historical_avg_minutes and historical_avg_minutes > 0:
            estimated = 0.7 * estimated + 0.3 * historical_avg_minutes

        # Clamp to reasonable bounds
        return max(5, min(60, int(round(estimated))))


# ============================================================================
# R3: Skill-based Agent-Client Assignment
# ============================================================================

@dataclass
class AgentSkills:
    """Agent competency profile for skill-based routing."""

    agent_id: UUID
    name: str

    # Core skills (1-5 scale)
    negotiation_level: int = 3
    product_knowledge: int = 3
    territory_experience_months: int = 12

    # Performance metrics (0-1 scale)
    conversion_rate: float = 0.7
    on_time_rate: float = 0.85
    customer_satisfaction: float = 0.8

    # Specializations
    handles_key_accounts: bool = False
    handles_new_clients: bool = False
    debt_collection_certified: bool = False

    # Languages (for diverse markets)
    languages: list[str] = field(default_factory=lambda: ["uz", "ru"])


class SkillBasedAssignment:
    """
    Calculate agent-client fit scores for optimal assignment.

    Considers agent skills, client requirements, and historical performance.
    """

    # Weight profiles for different client categories
    WEIGHT_PROFILES = {
        "A": {
            "negotiation": 0.35,
            "product_knowledge": 0.25,
            "experience": 0.15,
            "conversion": 0.15,
            "satisfaction": 0.10,
        },
        "B": {
            "negotiation": 0.20,
            "product_knowledge": 0.25,
            "experience": 0.25,
            "conversion": 0.15,
            "satisfaction": 0.15,
        },
        "C": {
            "negotiation": 0.10,
            "product_knowledge": 0.15,
            "experience": 0.30,
            "conversion": 0.25,
            "satisfaction": 0.20,
        },
    }

    @classmethod
    def calculate_fit_score(
        cls,
        agent: AgentSkills,
        client_category: str,
        is_new_client: bool = False,
        has_debt: bool = False,
        requires_language: Optional[str] = None,
    ) -> float:
        """
        Calculate fit score between agent and client.

        Returns:
            Score from 0.0 to 1.0 (higher = better fit)
        """
        weights = cls.WEIGHT_PROFILES.get(client_category.upper(), cls.WEIGHT_PROFILES["B"])

        # Normalize skills to 0-1 scale
        negotiation_norm = agent.negotiation_level / 5.0
        knowledge_norm = agent.product_knowledge / 5.0
        experience_norm = min(agent.territory_experience_months / 24.0, 1.0)  # Cap at 2 years

        # Calculate weighted score
        score = (
            weights["negotiation"] * negotiation_norm +
            weights["product_knowledge"] * knowledge_norm +
            weights["experience"] * experience_norm +
            weights["conversion"] * agent.conversion_rate +
            weights["satisfaction"] * agent.customer_satisfaction
        )

        # Bonus for specialized capabilities
        if client_category.upper() == "A" and agent.handles_key_accounts:
            score += 0.1

        if is_new_client and agent.handles_new_clients:
            score += 0.1

        if has_debt and agent.debt_collection_certified:
            score += 0.15

        # Language requirement penalty
        if requires_language and requires_language not in agent.languages:
            score *= 0.5  # Significant penalty

        return min(1.0, score)

    @classmethod
    def rank_agents_for_client(
        cls,
        agents: list[AgentSkills],
        client_category: str,
        is_new_client: bool = False,
        has_debt: bool = False,
        requires_language: Optional[str] = None,
    ) -> list[tuple[AgentSkills, float]]:
        """
        Rank agents by fit score for a specific client.

        Returns:
            List of (agent, score) tuples sorted by score descending
        """
        scored = [
            (agent, cls.calculate_fit_score(
                agent, client_category, is_new_client, has_debt, requires_language
            ))
            for agent in agents
        ]
        return sorted(scored, key=lambda x: x[1], reverse=True)


# ============================================================================
# R4: Predictive Visit Frequency
# ============================================================================

@dataclass
class ClientVisitFeatures:
    """Features for visit frequency prediction."""

    client_id: UUID
    category: str

    # Stock indicators
    stock_days_remaining: Optional[int] = None
    avg_daily_sales_units: float = 0.0

    # Financial indicators
    outstanding_debt: float = 0.0
    payment_reliability_score: float = 0.8  # 0-1

    # Engagement indicators
    days_since_last_order: int = 0
    days_since_last_visit: int = 0
    churn_risk_score: float = 0.0

    # Value indicators
    avg_order_value: float = 0.0
    lifetime_value: float = 0.0

    # Seasonality
    is_peak_season: bool = False
    has_active_promo: bool = False


class PredictiveVisitFrequency:
    """
    Predict optimal visit frequency for clients.

    Uses rule-based scoring with configurable weights.
    Can be replaced with ML model in production.
    """

    # Base frequencies by category (visits per week)
    BASE_FREQUENCIES = {
        "A": 2.0,
        "B": 1.0,
        "C": 0.5,
    }

    # Maximum frequency cap
    MAX_FREQUENCY = 3.0
    MIN_FREQUENCY = 0.25  # Once per month minimum

    @classmethod
    def predict(cls, features: ClientVisitFeatures) -> float:
        """
        Predict optimal visit frequency (visits per week).

        Returns:
            Recommended visits per week (0.25 to 3.0)
        """
        base = cls.BASE_FREQUENCIES.get(features.category.upper(), 1.0)

        # Adjustment factors
        adjustment = 0.0

        # Stock urgency (biggest factor)
        if features.stock_days_remaining is not None:
            if features.stock_days_remaining < 3:
                adjustment += 1.0  # Critical - visit ASAP
            elif features.stock_days_remaining < 7:
                adjustment += 0.5
            elif features.stock_days_remaining > 21:
                adjustment -= 0.25  # Well stocked

        # Churn risk
        if features.churn_risk_score > 0.7:
            adjustment += 0.75
        elif features.churn_risk_score > 0.5:
            adjustment += 0.25

        # Days since last order (engagement decay)
        if features.days_since_last_order > 14:
            adjustment += 0.5
        elif features.days_since_last_order > 7:
            adjustment += 0.25

        # High value clients get more attention
        if features.avg_order_value > 5000:
            adjustment += 0.25

        # Debt collection
        if features.outstanding_debt > 1000:
            adjustment += 0.25

        # Seasonal adjustments
        if features.is_peak_season:
            adjustment += 0.5
        if features.has_active_promo:
            adjustment += 0.25

        # Calculate final frequency
        frequency = base + adjustment

        return max(cls.MIN_FREQUENCY, min(cls.MAX_FREQUENCY, frequency))

    @classmethod
    def to_weekly_visits(cls, frequency: float, week_number: int) -> int:
        """
        Convert frequency to concrete number of visits for a specific week.

        Handles fractional frequencies (e.g., 0.5 = every other week).
        """
        if frequency >= 1.0:
            return int(round(frequency))
        else:
            # For frequencies < 1, use week number to determine if this week
            period = int(round(1.0 / frequency))
            if week_number % period == 0:
                return 1
            return 0


# ============================================================================
# R5: Traffic Multipliers by Time of Day
# ============================================================================

@dataclass
class TrafficProfile:
    """Traffic congestion profile for a region."""

    region: str
    timezone: str

    # Peak hours with multipliers
    morning_peak_start: time = time(7, 30)
    morning_peak_end: time = time(10, 0)
    morning_peak_multiplier: float = 1.8

    lunch_start: time = time(12, 0)
    lunch_end: time = time(14, 0)
    lunch_multiplier: float = 1.2

    evening_peak_start: time = time(17, 0)
    evening_peak_end: time = time(20, 0)
    evening_peak_multiplier: float = 2.0

    off_peak_multiplier: float = 1.0


class TrafficAwareETA:
    """
    Adjust travel times based on traffic patterns.

    Provides region-specific traffic multipliers for more accurate ETA.
    """

    # Predefined profiles for Central Asia
    PROFILES = {
        "tashkent": TrafficProfile(
            region="tashkent",
            timezone="Asia/Tashkent",
            morning_peak_start=time(7, 30),
            morning_peak_end=time(9, 30),
            morning_peak_multiplier=1.6,
            evening_peak_start=time(17, 0),
            evening_peak_end=time(19, 30),
            evening_peak_multiplier=1.7,
        ),
        "almaty": TrafficProfile(
            region="almaty",
            timezone="Asia/Almaty",
            morning_peak_start=time(7, 30),
            morning_peak_end=time(10, 0),
            morning_peak_multiplier=2.0,  # Almaty has worse traffic
            evening_peak_start=time(17, 0),
            evening_peak_end=time(20, 0),
            evening_peak_multiplier=2.2,
        ),
        "samarkand": TrafficProfile(
            region="samarkand",
            timezone="Asia/Tashkent",
            morning_peak_multiplier=1.3,
            evening_peak_multiplier=1.4,
        ),
        "default": TrafficProfile(
            region="default",
            timezone="UTC",
            morning_peak_multiplier=1.5,
            evening_peak_multiplier=1.5,
        ),
    }

    @classmethod
    def get_multiplier(
        cls,
        departure_time: time,
        region: str = "default",
    ) -> float:
        """
        Get traffic multiplier for given time and region.

        Returns:
            Multiplier to apply to OSRM travel times (1.0 = no change)
        """
        profile = cls.PROFILES.get(region.lower(), cls.PROFILES["default"])

        # Check morning peak
        if profile.morning_peak_start <= departure_time <= profile.morning_peak_end:
            return profile.morning_peak_multiplier

        # Check lunch
        if profile.lunch_start <= departure_time <= profile.lunch_end:
            return profile.lunch_multiplier

        # Check evening peak
        if profile.evening_peak_start <= departure_time <= profile.evening_peak_end:
            return profile.evening_peak_multiplier

        return profile.off_peak_multiplier

    @classmethod
    def adjust_duration(
        cls,
        osrm_duration_seconds: int,
        departure_time: time,
        region: str = "default",
    ) -> int:
        """
        Adjust OSRM duration with traffic multiplier.

        Returns:
            Adjusted duration in seconds
        """
        multiplier = cls.get_multiplier(departure_time, region)
        return int(osrm_duration_seconds * multiplier)

    @classmethod
    def estimate_arrival(
        cls,
        departure: datetime,
        osrm_duration_seconds: int,
        region: str = "default",
    ) -> datetime:
        """
        Estimate arrival time considering traffic.

        For long trips, applies different multipliers for different segments.
        """
        if osrm_duration_seconds < 1800:  # Less than 30 min
            # Simple case: single multiplier
            adjusted = cls.adjust_duration(
                osrm_duration_seconds,
                departure.time(),
                region
            )
            return departure + timedelta(seconds=adjusted)

        # For longer trips, segment by hour
        total_adjusted = 0
        remaining = osrm_duration_seconds
        current_time = departure

        while remaining > 0:
            # Calculate segment (up to next hour boundary)
            segment = min(remaining, 3600)
            multiplier = cls.get_multiplier(current_time.time(), region)
            total_adjusted += int(segment * multiplier)

            remaining -= segment
            current_time += timedelta(seconds=segment)

        return departure + timedelta(seconds=total_adjusted)


# ============================================================================
# R6: ETA Calibration Service
# ============================================================================

@dataclass
class ETACalibrationData:
    """Historical data point for ETA calibration."""

    from_location: tuple[float, float]
    to_location: tuple[float, float]
    planned_duration_seconds: int
    actual_duration_seconds: int
    departure_hour: int
    day_of_week: int
    region: str


class ETACalibrationService:
    """
    Learn and apply ETA adjustments from historical data.

    Stores adjustment factors by:
    - Hour of day
    - Day of week
    - Region
    """

    def __init__(self):
        # Adjustment factors: region -> hour -> day_of_week -> factor
        self._adjustments: dict[str, dict[int, dict[int, float]]] = {}
        self._sample_counts: dict[str, dict[int, dict[int, int]]] = {}

    def record_actual(
        cls,
        planned_seconds: int,
        actual_seconds: int,
        departure_hour: int,
        day_of_week: int,
        region: str,
    ) -> None:
        """
        Record actual vs planned duration for calibration.

        Uses exponential moving average for smooth updates.
        """
        if region not in cls._adjustments:
            cls._adjustments[region] = {}
            cls._sample_counts[region] = {}

        if departure_hour not in cls._adjustments[region]:
            cls._adjustments[region][departure_hour] = {}
            cls._sample_counts[region][departure_hour] = {}

        if day_of_week not in cls._adjustments[region][departure_hour]:
            cls._adjustments[region][departure_hour][day_of_week] = 1.0
            cls._sample_counts[region][departure_hour][day_of_week] = 0

        # Calculate error ratio
        if planned_seconds > 0:
            error_ratio = actual_seconds / planned_seconds
        else:
            error_ratio = 1.0

        # Update with EMA (alpha = 0.1 for smooth updates)
        alpha = 0.1
        current = cls._adjustments[region][departure_hour][day_of_week]
        cls._adjustments[region][departure_hour][day_of_week] = (
            alpha * error_ratio + (1 - alpha) * current
        )
        cls._sample_counts[region][departure_hour][day_of_week] += 1

    def get_calibration_factor(
        cls,
        departure_hour: int,
        day_of_week: int,
        region: str,
    ) -> float:
        """
        Get calibration factor for given conditions.

        Returns:
            Factor to multiply estimated duration (1.0 = no adjustment)
        """
        try:
            factor = cls._adjustments[region][departure_hour][day_of_week]
            count = cls._sample_counts[region][departure_hour][day_of_week]

            # Only trust if we have enough samples
            if count < 10:
                return 1.0  # Not enough data

            # Clamp to reasonable range
            return max(0.5, min(2.0, factor))
        except KeyError:
            return 1.0

    def calibrate_duration(
        cls,
        base_duration_seconds: int,
        departure: datetime,
        region: str,
    ) -> int:
        """
        Apply calibration to base duration estimate.

        Combines traffic multiplier with learned calibration.
        """
        # First apply traffic multiplier
        traffic_adjusted = TrafficAwareETA.adjust_duration(
            base_duration_seconds,
            departure.time(),
            region,
        )

        # Then apply learned calibration
        calibration = cls.get_calibration_factor(
            departure.hour,
            departure.weekday(),
            region,
        )

        return int(traffic_adjusted * calibration)


# ============================================================================
# R8: Smart Priority Refresh
# ============================================================================

class SmartPriorityRefresh:
    """
    Mid-day priority recalculation for remaining visits.

    Triggers at 13:00 (after lunch) to re-evaluate afternoon priorities
    based on morning outcomes and real-time data.
    """

    REFRESH_HOUR = 13  # 1 PM
    PRIORITY_CHANGE_THRESHOLD = 15  # Minimum change to trigger reorder

    @classmethod
    def calculate_afternoon_priority(
        cls,
        client_category: str,
        base_priority: int,
        stock_days: Optional[int],
        outstanding_debt: float,
        is_payday_window: bool,
        churn_risk: float,
        morning_competitor_visit: bool = False,
        morning_order_elsewhere: bool = False,
    ) -> int:
        """
        Calculate updated priority for afternoon visits.

        Considers:
        - Real-time stock levels
        - Payday window (remaining hours)
        - Morning intelligence (competitor activity)
        """
        score = base_priority * 10

        # Stock urgency (may have changed since morning)
        if stock_days is not None:
            if stock_days < 2:
                score += 35  # More urgent than morning
            elif stock_days < 5:
                score += 20

        # Payday urgency increases in afternoon
        if outstanding_debt > 0 and is_payday_window:
            score += 30  # Higher than morning (less time remaining)
        elif outstanding_debt > 0:
            score += 10

        # Churn risk
        if churn_risk > 0.7:
            score += 25
        elif churn_risk > 0.5:
            score += 10

        # Morning intelligence adjustments
        if morning_competitor_visit:
            score += 25  # Visit ASAP to counter

        if morning_order_elsewhere:
            score -= 20  # Lower priority - already ordered

        return min(100, max(0, score))

    @classmethod
    def should_reorder(
        cls,
        old_priorities: list[int],
        new_priorities: list[int],
    ) -> bool:
        """
        Determine if priority changes warrant route reordering.

        Returns True if significant changes detected.
        """
        if len(old_priorities) != len(new_priorities):
            return True

        # Check for significant individual changes
        for old, new in zip(old_priorities, new_priorities):
            if abs(old - new) >= cls.PRIORITY_CHANGE_THRESHOLD:
                return True

        # Check if ordering would change
        old_order = sorted(range(len(old_priorities)), key=lambda i: old_priorities[i], reverse=True)
        new_order = sorted(range(len(new_priorities)), key=lambda i: new_priorities[i], reverse=True)

        return old_order != new_order


# ============================================================================
# R10: Visit Outcome Feedback
# ============================================================================

class VisitOutcome(str, enum.Enum):
    """Possible outcomes of a client visit."""

    SUCCESSFUL_ORDER = "successful_order"
    NO_ORDER_STOCK_OK = "no_order_stock_ok"
    NO_ORDER_NO_BUDGET = "no_order_no_budget"
    NO_ORDER_PRICE_ISSUE = "no_order_price_issue"
    CLIENT_UNAVAILABLE = "client_unavailable"
    CLIENT_CLOSED = "client_closed"
    COMPETITOR_PRESENT = "competitor_present"
    COMPETITOR_JUST_VISITED = "competitor_just_visited"
    RESCHEDULED = "rescheduled"
    CANCELLED_BY_CLIENT = "cancelled_by_client"


@dataclass
class VisitFeedback:
    """Feedback data from a completed visit."""

    visit_id: UUID
    client_id: UUID
    agent_id: UUID
    outcome: VisitOutcome

    # Timing
    planned_arrival: datetime
    actual_arrival: Optional[datetime] = None
    actual_departure: Optional[datetime] = None

    # Order data (if applicable)
    order_value: float = 0.0
    order_sku_count: int = 0

    # Intelligence
    competitor_name: Optional[str] = None
    client_feedback: Optional[str] = None
    next_preferred_time: Optional[time] = None

    # Calculated
    was_on_time: bool = True
    wait_time_minutes: int = 0


class VisitFeedbackProcessor:
    """
    Process visit outcomes to improve future planning.

    Updates client profiles, adjusts frequencies, and feeds
    data to calibration services.
    """

    # Outcome impact on visit frequency
    FREQUENCY_ADJUSTMENTS = {
        VisitOutcome.SUCCESSFUL_ORDER: 0.0,  # No change
        VisitOutcome.NO_ORDER_STOCK_OK: -0.1,  # Slightly reduce
        VisitOutcome.NO_ORDER_NO_BUDGET: 0.0,
        VisitOutcome.CLIENT_UNAVAILABLE: 0.0,  # Find better time
        VisitOutcome.COMPETITOR_PRESENT: +0.5,  # Increase frequency
        VisitOutcome.COMPETITOR_JUST_VISITED: +0.3,
    }

    # Outcome impact on churn risk
    CHURN_RISK_ADJUSTMENTS = {
        VisitOutcome.SUCCESSFUL_ORDER: -0.05,
        VisitOutcome.NO_ORDER_NO_BUDGET: +0.05,
        VisitOutcome.NO_ORDER_PRICE_ISSUE: +0.1,
        VisitOutcome.COMPETITOR_PRESENT: +0.15,
        VisitOutcome.COMPETITOR_JUST_VISITED: +0.1,
        VisitOutcome.CANCELLED_BY_CLIENT: +0.1,
    }

    @classmethod
    def process(cls, feedback: VisitFeedback) -> dict:
        """
        Process visit feedback and return recommended updates.

        Returns:
            Dictionary of recommended client/agent updates
        """
        updates = {
            "client_updates": {},
            "agent_updates": {},
            "planning_hints": {},
        }

        # Frequency adjustment
        freq_adj = cls.FREQUENCY_ADJUSTMENTS.get(feedback.outcome, 0.0)
        if freq_adj != 0:
            updates["client_updates"]["frequency_adjustment"] = freq_adj

        # Churn risk adjustment
        churn_adj = cls.CHURN_RISK_ADJUSTMENTS.get(feedback.outcome, 0.0)
        if churn_adj != 0:
            updates["client_updates"]["churn_risk_adjustment"] = churn_adj

        # Preferred visit time (if client was unavailable)
        if feedback.outcome == VisitOutcome.CLIENT_UNAVAILABLE:
            if feedback.next_preferred_time:
                updates["client_updates"]["preferred_visit_time"] = feedback.next_preferred_time

        # Competitor intelligence
        if feedback.outcome in (VisitOutcome.COMPETITOR_PRESENT, VisitOutcome.COMPETITOR_JUST_VISITED):
            updates["planning_hints"]["competitor_alert"] = True
            updates["planning_hints"]["competitor_name"] = feedback.competitor_name
            updates["client_updates"]["competitive_pressure"] = True

        # Agent performance tracking
        if feedback.actual_arrival and feedback.planned_arrival:
            delay_minutes = (feedback.actual_arrival - feedback.planned_arrival).total_seconds() / 60
            updates["agent_updates"]["delay_minutes"] = delay_minutes

            if delay_minutes > 15:
                updates["agent_updates"]["late_arrival"] = True

        # Service time learning
        if feedback.actual_arrival and feedback.actual_departure:
            actual_duration = (feedback.actual_departure - feedback.actual_arrival).total_seconds() / 60
            updates["client_updates"]["last_visit_duration_minutes"] = actual_duration

        return updates


# ============================================================================
# R11: Customer Satisfaction Scoring
# ============================================================================

@dataclass
class ClientSatisfactionInputs:
    """Input data for satisfaction score calculation."""

    client_id: UUID

    # Visit quality (last 90 days)
    total_visits: int = 0
    on_time_visits: int = 0
    successful_orders: int = 0

    # Service quality
    avg_visit_duration_vs_expected: float = 1.0  # <1 = rushed, >1 = thorough
    complaints_count: int = 0

    # Fulfillment
    orders_placed: int = 0
    orders_fulfilled: int = 0
    orders_on_time: int = 0

    # Engagement
    promo_offers_received: int = 0
    promo_offers_accepted: int = 0

    # Frequency satisfaction
    requested_frequency: float = 1.0  # visits/week
    actual_frequency: float = 1.0


class CustomerSatisfactionScore:
    """
    Calculate customer satisfaction score (0-100).

    Combines multiple factors into a single score for
    monitoring and prioritization.
    """

    # Component weights
    WEIGHTS = {
        "visit_punctuality": 0.20,
        "visit_coverage": 0.15,
        "order_conversion": 0.15,
        "fulfillment_rate": 0.20,
        "fulfillment_timeliness": 0.10,
        "complaint_absence": 0.10,
        "promo_engagement": 0.05,
        "service_thoroughness": 0.05,
    }

    @classmethod
    def calculate(cls, inputs: ClientSatisfactionInputs) -> float:
        """
        Calculate satisfaction score (0-100).

        Higher scores indicate more satisfied customers.
        """
        scores = {}

        # Visit punctuality (% on-time)
        if inputs.total_visits > 0:
            scores["visit_punctuality"] = inputs.on_time_visits / inputs.total_visits
        else:
            scores["visit_punctuality"] = 0.5  # Neutral if no visits

        # Visit coverage (actual vs requested frequency)
        if inputs.requested_frequency > 0:
            coverage = inputs.actual_frequency / inputs.requested_frequency
            scores["visit_coverage"] = min(1.0, coverage)  # Cap at 100%
        else:
            scores["visit_coverage"] = 1.0

        # Order conversion (% visits resulting in orders)
        if inputs.total_visits > 0:
            scores["order_conversion"] = inputs.successful_orders / inputs.total_visits
        else:
            scores["order_conversion"] = 0.5

        # Fulfillment rate
        if inputs.orders_placed > 0:
            scores["fulfillment_rate"] = inputs.orders_fulfilled / inputs.orders_placed
        else:
            scores["fulfillment_rate"] = 1.0  # No orders = no issues

        # Fulfillment timeliness
        if inputs.orders_fulfilled > 0:
            scores["fulfillment_timeliness"] = inputs.orders_on_time / inputs.orders_fulfilled
        else:
            scores["fulfillment_timeliness"] = 1.0

        # Complaint absence (inverse of complaints)
        complaint_penalty = min(inputs.complaints_count * 0.2, 1.0)
        scores["complaint_absence"] = 1.0 - complaint_penalty

        # Promo engagement
        if inputs.promo_offers_received > 0:
            scores["promo_engagement"] = inputs.promo_offers_accepted / inputs.promo_offers_received
        else:
            scores["promo_engagement"] = 0.5

        # Service thoroughness (not rushed)
        # Score is best at 1.0 (expected duration), penalize both rushed and too long
        deviation = abs(inputs.avg_visit_duration_vs_expected - 1.0)
        scores["service_thoroughness"] = max(0, 1.0 - deviation)

        # Calculate weighted sum
        total = sum(
            cls.WEIGHTS[component] * scores[component]
            for component in cls.WEIGHTS
        )

        return round(total * 100, 1)

    @classmethod
    def get_risk_level(cls, score: float) -> str:
        """
        Get risk level from satisfaction score.

        Returns:
            'low', 'medium', 'high', or 'critical'
        """
        if score >= 80:
            return "low"
        elif score >= 60:
            return "medium"
        elif score >= 40:
            return "high"
        else:
            return "critical"

    @classmethod
    def get_improvement_suggestions(
        cls,
        inputs: ClientSatisfactionInputs,
    ) -> list[str]:
        """
        Get actionable suggestions to improve satisfaction.
        """
        suggestions = []

        # Check visit punctuality
        if inputs.total_visits > 0:
            on_time_rate = inputs.on_time_visits / inputs.total_visits
            if on_time_rate < 0.8:
                suggestions.append(
                    f"Improve visit punctuality (currently {on_time_rate:.0%}). "
                    "Consider adjusting route schedule or traffic estimates."
                )

        # Check visit coverage
        if inputs.requested_frequency > 0:
            coverage = inputs.actual_frequency / inputs.requested_frequency
            if coverage < 0.9:
                suggestions.append(
                    f"Increase visit frequency to match client expectations "
                    f"(current: {coverage:.0%} of requested)."
                )

        # Check conversion
        if inputs.total_visits > 5:  # Need enough data
            conversion = inputs.successful_orders / inputs.total_visits
            if conversion < 0.6:
                suggestions.append(
                    f"Low order conversion ({conversion:.0%}). "
                    "Review pricing, stock availability, or sales approach."
                )

        # Check fulfillment
        if inputs.orders_placed > 0:
            fulfillment = inputs.orders_fulfilled / inputs.orders_placed
            if fulfillment < 0.95:
                suggestions.append(
                    f"Fulfillment rate ({fulfillment:.0%}) below target. "
                    "Address supply chain or inventory issues."
                )

        # Check complaints
        if inputs.complaints_count > 0:
            suggestions.append(
                f"{inputs.complaints_count} complaints recorded. "
                "Review and address root causes."
            )

        return suggestions
