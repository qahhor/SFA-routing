"""
Routing API Endpoints.

TSP - Traveling Salesperson Problem
VRPC - Vehicle Routing Problem with Capacity Constraints

Based on Google OR-Tools routing services.
"""

import logging
from typing import Union

from fastapi import APIRouter, status

from app.schemas.field_routing import (
    TSPAutoResponse,
    TSPRequest,
    TSPSingleResponse,
    VRPCRequest,
    VRPCResponse,
)
from app.services.planning.field_routing import tsp_service, vrpc_service

logger = logging.getLogger(__name__)

# TSP Router - mounted at /api/v1
tsp_router = APIRouter(tags=["TSP - Traveling Salesperson Problem"])

# VRPC Router - mounted at /vrpc
vrpc_router = APIRouter(
    prefix="/vrpc", tags=["VRPC - Vehicle Routing Problem"]
)


# ============================================================
# TSP Endpoints
# ============================================================


@tsp_router.post(
    "/tsp",
    response_model=Union[TSPAutoResponse, TSPSingleResponse],
    status_code=status.HTTP_200_OK,
    summary="Solve Traveling Salesperson Problem",
    description="""
    Generates route for a salesperson who must visit a number of points
    each day for four weeks.

    ## Kinds

    - **auto**: Generate multiple optimal plans (with clustering)
    - **single**: Generate one optimal plan

    ## Visit Intensities

    - `THREE_TIMES_A_WEEK` - 3 visits per week (Mon, Wed, Fri)
    - `TWO_TIMES_A_WEEK` - 2 visits per week (Mon, Thu)
    - `ONCE_A_WEEK` - 1 visit per week
    - `ONCE_IN_TWO_WEEKS` - 1 visit per 2 weeks
    - `ONCE_A_MONTH` - 1 visit per month

    ## Response Codes

    - **100**: Success
    - **101**: Invalid input format
    - **104**: OSRM connection error
    - **105**: OSRM matrix error
    - **108**: Time limit reached
    - **109**: No solution found
    - **110**: Unexpected error
    - **111**: Out of memory
    """,
    responses={
        200: {
            "description": "TSP solution",
            "content": {
                "application/json": {
                    "examples": {
                        "auto_success": {
                            "summary": "Auto mode success",
                            "value": {
                                "code": 100,
                                "plans": [
                                    [
                                        {
                                            "weekNumber": 1,
                                            "days": [
                                                {
                                                    "dayNumber": 1,
                                                    "route": ["loc-1"],
                                                    "totalDuration": 120,
                                                    "totalDistance": 15.5,
                                                }
                                            ],
                                        }
                                    ]
                                ],
                            },
                        },
                        "single_success": {
                            "summary": "Single mode success",
                            "value": {
                                "code": 100,
                                "weeks": [
                                    {
                                        "weekNumber": 1,
                                        "days": [
                                            {
                                                "dayNumber": 1,
                                                "route": ["loc-1", "loc-2"],
                                                "totalDuration": 180,
                                                "totalDistance": 22.3,
                                            }
                                        ],
                                    }
                                ],
                            },
                        },
                        "error": {
                            "summary": "Error response",
                            "value": {
                                "code": 109,
                                "error_text": "No solution found",
                            },
                        },
                    }
                }
            },
        },
    },
)
async def solve_tsp(
    request: TSPRequest,
) -> Union[TSPAutoResponse, TSPSingleResponse]:
    """
    Solve Traveling Salesperson Problem.

    The service calculates the route based on the time to travel between
    points and the time spent at each point. Returns the route with
    minimum time spent on the road.

    Constraints:
    - Working hours per day (8 hours)
    - Visit duration at each point
    - Intensity of visits at each point
    - Working days for each location
    """
    logger.info(
        f"TSP request: kind={request.kind.value}, "
        f"locations={len(request.locations)}"
    )

    response = await tsp_service.solve(request)

    logger.info(f"TSP response: code={response.code}")

    return response


# ============================================================
# VRPC Endpoints
# ============================================================


@vrpc_router.post(
    "",
    response_model=VRPCResponse,
    status_code=status.HTTP_200_OK,
    summary="Solve Vehicle Routing Problem with Capacity Constraints",
    description="""
    Solves vehicle routing problem where multiple vehicles with
    capacity constraints must visit delivery points starting and
    ending at a depot.

    ## Features

    - Multiple vehicles with different types and capacities
    - Vehicle types: car, truck, walking, cycling
    - Depot as start/end location
    - Maximum cycle distance constraint
    - Global span coefficient for balancing distance vs time

    ## Response Codes

    - **100**: Success
    - **101**: Invalid input format
    - **102**: Unsupported vehicle type
    - **103**: URL not found for vehicle type
    - **104**: OSRM connection error
    - **105**: OSRM matrix error
    - **106**: Weight exceeds vehicle capacity
    - **107**: Arc cost not set
    - **108**: Time limit reached
    - **109**: No solution found
    - **110**: Unexpected error
    - **111**: Out of memory
    """,
    responses={
        200: {
            "description": "VRPC solution",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "summary": "Success response",
                            "value": {
                                "code": 100,
                                "vehicles": [
                                    [
                                        {
                                            "route": [2, 5, 4],
                                            "distance": 12423,
                                            "duration": 52,
                                        },
                                        {
                                            "route": [1, 7],
                                            "distance": 12423,
                                            "duration": 52,
                                        },
                                    ],
                                    [
                                        {
                                            "route": [3, 6],
                                            "distance": 42423,
                                            "duration": 184,
                                        }
                                    ],
                                ],
                                "total_distance": 56230,
                                "total_duration": 245,
                            },
                        },
                        "error": {
                            "summary": "Error response",
                            "value": {
                                "code": 106,
                                "error_text": "The weight of the load exceeds "
                                "the carrying capacity of the vehicle.",
                            },
                        },
                    }
                }
            },
        },
    },
)
async def solve_vrpc(
    request: VRPCRequest,
) -> VRPCResponse:
    """
    Solve Vehicle Routing Problem with Capacity Constraints.

    Vehicles start and end their trips at the depot. Each vehicle
    can make multiple loops/trips. Points are assigned to vehicles
    based on capacity and distance constraints.
    """
    logger.info(
        f"VRPC request: points={len(request.points)}, "
        f"vehicles={len(request.vehicles)}"
    )

    response = await vrpc_service.solve(request)

    logger.info(
        f"VRPC response: code={response.code}, "
        f"total_distance={response.total_distance}"
    )

    return response


# Combined router for backward compatibility
router = APIRouter()
router.include_router(tsp_router)
router.include_router(vrpc_router)
