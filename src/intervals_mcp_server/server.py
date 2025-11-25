"""
Intervals.icu MCP Server

This module implements a Model Context Protocol (MCP) server for connecting
Claude with the Intervals.icu API. It provides tools for retrieving and managing
athlete data, including activities, events, workouts, and wellness metrics.

Main Features:
    - Activity retrieval and detailed analysis
    - Event management (races, workouts, calendar items)
    - Wellness data tracking and visualization
    - Error handling with user-friendly messages
    - Configurable parameters with environment variable support

Usage:
    This server is designed to be run as a standalone script and exposes several MCP tools
    for use with Claude Desktop or other MCP-compatible clients. The server loads configuration
    from environment variables (optionally via a .env file) and communicates with the Intervals.icu API.

    To run the server:
        $ python src/intervals_mcp_server/server.py

    MCP tools provided:
        - get_activities
        - get_activity_details
        - get_events
        - get_event_by_id
        - get_wellness_data
        - get_activity_intervals
        - add_events

    See the README for more details on configuration and usage.
"""

from json import JSONDecodeError
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any
import json

import httpx  # pylint: disable=import-error
from mcp.server.fastmcp import FastMCP  # pylint: disable=import-error

# Import formatting utilities
from intervals_mcp_server.utils.formatting import (
    format_activity_summary,
    format_event_details,
    format_event_summary,
    format_intervals,
    format_wellness_entry,
)

from intervals_mcp_server.utils.types import WorkoutDoc

# Try to load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv

    _ = load_dotenv()
except ImportError:
    # python-dotenv not installed, proceed without it
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("intervals_icu_mcp_server")

# Create a single AsyncClient instance for all requests
httpx_client = httpx.AsyncClient()


@asynccontextmanager
async def lifespan(_app: FastMCP):
    """
    Context manager to ensure the shared httpx client is closed when the server stops.

    Args:
        _app (FastMCP): The MCP server application instance.
    """
    try:
        yield
    finally:
        await httpx_client.aclose()


# Initialize FastMCP server with custom lifespan
mcp = FastMCP("intervals-icu", lifespan=lifespan)

# Constants
INTERVALS_API_BASE_URL = os.getenv("INTERVALS_API_BASE_URL", "https://intervals.icu/api/v1")
API_KEY = os.getenv("API_KEY", "")  # Provide default empty string
ATHLETE_ID = os.getenv("ATHLETE_ID", "")  # Default athlete ID from .env
USER_AGENT = "intervalsicu-mcp-server/1.0"

# Accept athlete IDs that are either all digits or start with 'i' followed by digits
if not re.fullmatch(r"i?\d+", ATHLETE_ID):
    raise ValueError(
        "ATHLETE_ID must be all digits (e.g. 123456) or start with 'i' followed by digits (e.g. i123456)"
    )


def validate_date(date_str: str) -> str:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError as e:
        raise ValueError("Invalid date format. Please use YYYY-MM-DD.") from e


def _get_error_message(error_code: int, error_text: str) -> str:
    """Return a user-friendly error message for a given HTTP status code."""
    error_messages = {
        HTTPStatus.UNAUTHORIZED: f"{HTTPStatus.UNAUTHORIZED.value} {HTTPStatus.UNAUTHORIZED.phrase}: Please check your API key.",
        HTTPStatus.FORBIDDEN: f"{HTTPStatus.FORBIDDEN.value} {HTTPStatus.FORBIDDEN.phrase}: You may not have permission to access this resource.",
        HTTPStatus.NOT_FOUND: f"{HTTPStatus.NOT_FOUND.value} {HTTPStatus.NOT_FOUND.phrase}: The requested endpoint or ID doesn't exist.",
        HTTPStatus.UNPROCESSABLE_ENTITY: f"{HTTPStatus.UNPROCESSABLE_ENTITY.value} {HTTPStatus.UNPROCESSABLE_ENTITY.phrase}: The server couldn't process the request (invalid parameters or unsupported operation).",
        HTTPStatus.TOO_MANY_REQUESTS: f"{HTTPStatus.TOO_MANY_REQUESTS.value} {HTTPStatus.TOO_MANY_REQUESTS.phrase}: Too many requests in a short time period.",
        HTTPStatus.INTERNAL_SERVER_ERROR: f"{HTTPStatus.INTERNAL_SERVER_ERROR.value} {HTTPStatus.INTERNAL_SERVER_ERROR.phrase}: The Intervals.icu server encountered an internal error.",
        HTTPStatus.SERVICE_UNAVAILABLE: f"{HTTPStatus.SERVICE_UNAVAILABLE.value} {HTTPStatus.SERVICE_UNAVAILABLE.phrase}: The Intervals.icu server might be down or undergoing maintenance.",
    }
    try:
        status = HTTPStatus(error_code)
        return error_messages.get(status, error_text)
    except ValueError:
        return error_text


async def make_intervals_request(
    url: str,
    api_key: str | None = None,
    params: dict[str, Any] | None = None,
    method: str = "GET",
    data: dict[str, Any] | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    """
    Make a request to the Intervals.icu API with proper error handling.

    Args:
        url (str): The API endpoint path (e.g., '/athlete/{id}/activities').
        api_key (str | None): Optional API key to use for authentication. Defaults to the global API_KEY.
        params (dict[str, Any] | None): Optional query parameters for the request.
        method (str): HTTP method to use (GET, POST, etc.). Defaults to GET.
        data (dict[str, Any] | None): Optional data to send in the request body.

    Returns:
        dict[str, Any] | list[dict[str, Any]]: The parsed JSON response from the API, or an error dict.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    if method in ["POST", "PUT"]:
        headers["Content-Type"] = "application/json"

    # Use provided api_key or fall back to global API_KEY
    key_to_use = api_key if api_key is not None else API_KEY
    if not key_to_use:
        logger.error("No API key provided for request to: %s", url)
        return {
            "error": True,
            "message": "API key is required. Set API_KEY env var or pass api_key",
        }

    auth = httpx.BasicAuth("API_KEY", key_to_use)
    full_url = f"{INTERVALS_API_BASE_URL}{url}"

    try:
        if method == "POST" and data is not None:
            response = await httpx_client.request(
                method=method,
                url=full_url,
                headers=headers,
                params=params,
                auth=auth,
                timeout=30.0,
                content=json.dumps(data),
            )
        else:
            response = await httpx_client.request(
                method=method,
                url=full_url,
                headers=headers,
                params=params,
                auth=auth,
                timeout=30.0,
            )
        try:
            response_data = response.json() if response.content else {}
        except JSONDecodeError:
            logger.error("Invalid JSON in response from: %s", full_url)
            return {"error": True, "message": "Invalid JSON in response"}
        _ = response.raise_for_status()
        return response_data
    except httpx.HTTPStatusError as e:
        error_code = e.response.status_code
        error_text = e.response.text

        logger.error("HTTP error: %s - %s", error_code, error_text)

        return {
            "error": True,
            "status_code": error_code,
            "message": _get_error_message(error_code, error_text),
        }
    except httpx.RequestError as e:
        logger.error("Request error: %s", str(e))
        return {"error": True, "message": f"Request error: {str(e)}"}
    except httpx.HTTPError as e:
        logger.error("HTTP client error: %s", str(e))
        return {"error": True, "message": f"HTTP client error: {str(e)}"}


# ----- MCP Tool Implementations ----- #


def _parse_activities_from_result(result: Any) -> list[dict[str, Any]]:
    """Extract a list of activity dictionaries from the API result."""
    activities: list[dict[str, Any]] = []

    if isinstance(result, list):
        activities = [item for item in result if isinstance(item, dict)]
    elif isinstance(result, dict):
        # Result is a single activity or a container
        for _key, value in result.items():
            if isinstance(value, list):
                activities = [item for item in value if isinstance(item, dict)]
                break
        # If no list was found but the dict has typical activity fields, treat it as a single activity
        if not activities and any(key in result for key in ["name", "startTime", "distance"]):
            activities = [result]

    return activities


def _filter_named_activities(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter out unnamed activities from the list."""
    return [
        activity
        for activity in activities
        if activity.get("name") and activity.get("name") != "Unnamed"
    ]


async def _fetch_more_activities(
    athlete_id: str,
    start_date: str,
    api_key: str | None,
    api_limit: int,
) -> list[dict[str, Any]]:
    """Fetch additional activities from an earlier date range."""
    oldest_date = datetime.fromisoformat(start_date)
    older_start_date = (oldest_date - timedelta(days=60)).strftime("%Y-%m-%d")
    older_end_date = (oldest_date - timedelta(days=1)).strftime("%Y-%m-%d")

    if older_start_date >= older_end_date:
        return []

    more_params = {
        "oldest": older_start_date,
        "newest": older_end_date,
        "limit": api_limit,
    }
    more_result = await make_intervals_request(
        url=f"/athlete/{athlete_id}/activities",
        api_key=api_key,
        params=more_params,
    )

    if isinstance(more_result, list):
        return _filter_named_activities(more_result)
    return []


def _format_activities_response(
    activities: list[dict[str, Any]],
    athlete_id: str,
    include_unnamed: bool,
) -> str:
    """Format the activities response based on the results."""
    if not activities:
        if include_unnamed:
            return (
                f"No valid activities found for athlete {athlete_id} in the specified date range."
            )
        return f"No named activities found for athlete {athlete_id} in the specified date range. Try with include_unnamed=True to see all activities."

    # Format the output
    activities_summary = "Activities:\n\n"
    for activity in activities:
        if isinstance(activity, dict):
            activities_summary += format_activity_summary(activity) + "\n"
        else:
            activities_summary += f"Invalid activity format: {activity}\n\n"

    return activities_summary


@mcp.tool()
async def get_activities(  # pylint: disable=too-many-arguments,too-many-return-statements,too-many-branches,too-many-positional-arguments
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 10,
    include_unnamed: bool = False,
) -> str:
    """Get a list of activities for an athlete from Intervals.icu

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to 30 days ago)
        end_date: End date in YYYY-MM-DD format (optional, defaults to today)
        limit: Maximum number of activities to return (optional, defaults to 10)
        include_unnamed: Whether to include unnamed activities (optional, defaults to False)
    """
    # Use provided athlete_id or fall back to global ATHLETE_ID
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    # Parse date parameters
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    # Fetch more activities if we need to filter out unnamed ones
    api_limit = limit * 3 if not include_unnamed else limit

    # Call the Intervals.icu API
    params = {"oldest": start_date, "newest": end_date, "limit": api_limit}
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/activities", api_key=api_key, params=params
    )

    # Check for error
    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching activities: {error_message}"

    if not result:
        return f"No activities found for athlete {athlete_id_to_use} in the specified date range."

    # Parse activities from result
    activities = _parse_activities_from_result(result)

    if not activities:
        return f"No valid activities found for athlete {athlete_id_to_use} in the specified date range."

    # Filter and fetch more if needed
    if not include_unnamed:
        activities = _filter_named_activities(activities)

        # If we don't have enough named activities, try to fetch more
        if len(activities) < limit:
            more_activities = await _fetch_more_activities(
                athlete_id_to_use, start_date, api_key, api_limit
            )
            activities.extend(more_activities)

    # Limit to requested count
    activities = activities[:limit]

    return _format_activities_response(activities, athlete_id_to_use, include_unnamed)


@mcp.tool()
async def get_activity_details(activity_id: str, api_key: str | None = None) -> str:
    """Get detailed information for a specific activity from Intervals.icu

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Call the Intervals.icu API
    result = await make_intervals_request(url=f"/activity/{activity_id}", api_key=api_key)

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching activity details: {error_message}"

    # Format the response
    if not result:
        return f"No details found for activity {activity_id}."

    # If result is a list, use the first item if available
    activity_data = result[0] if isinstance(result, list) and result else result
    if not isinstance(activity_data, dict):
        return f"Invalid activity format for activity {activity_id}."

    # Return a more detailed view of the activity
    detailed_view = format_activity_summary(activity_data)

    # Add additional details if available
    if "zones" in activity_data:
        zones = activity_data["zones"]
        detailed_view += "\nPower Zones:\n"
        for zone in zones.get("power", []):
            detailed_view += f"Zone {zone.get('number')}: {zone.get('secondsInZone')} seconds\n"

        detailed_view += "\nHeart Rate Zones:\n"
        for zone in zones.get("hr", []):
            detailed_view += f"Zone {zone.get('number')}: {zone.get('secondsInZone')} seconds\n"

    return detailed_view


@mcp.tool()
async def get_activity_intervals(activity_id: str, api_key: str | None = None) -> str:
    """Get interval data for a specific activity from Intervals.icu

    This endpoint returns detailed metrics for each interval in an activity, including power, heart rate,
    cadence, speed, and environmental data. It also includes grouped intervals if applicable.

    Args:
        activity_id: The Intervals.icu activity ID
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Call the Intervals.icu API
    result = await make_intervals_request(url=f"/activity/{activity_id}/intervals", api_key=api_key)

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching intervals: {error_message}"

    # Format the response
    if not result:
        return f"No interval data found for activity {activity_id}."

    # If the result is empty or doesn't contain expected fields
    if not isinstance(result, dict) or not any(
        key in result for key in ["icu_intervals", "icu_groups"]
    ):
        return f"No interval data or unrecognized format for activity {activity_id}."

    # Format the intervals data
    return format_intervals(result)


@mcp.tool()
async def get_events(
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Get events for an athlete from Intervals.icu

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to today)
        end_date: End date in YYYY-MM-DD format (optional, defaults to 30 days from today)
    """
    # Use provided athlete_id or fall back to global ATHLETE_ID
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    # Parse date parameters
    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")
    if not end_date:
        end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    # Call the Intervals.icu API
    params = {"oldest": start_date, "newest": end_date}

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events", api_key=api_key, params=params
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching events: {error_message}"

    # Format the response
    if not result:
        return f"No events found for athlete {athlete_id_to_use} in the specified date range."

    # Ensure result is a list
    events = result if isinstance(result, list) else []

    if not events:
        return f"No events found for athlete {athlete_id_to_use} in the specified date range."

    events_summary = "Events:\n\n"
    for event in events:
        if not isinstance(event, dict):
            continue

        events_summary += format_event_summary(event) + "\n\n"

    return events_summary


@mcp.tool()
async def get_event_by_id(
    event_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get detailed information for a specific event from Intervals.icu

    Args:
        event_id: The Intervals.icu event ID
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    # Use provided athlete_id or fall back to global ATHLETE_ID
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    # Call the Intervals.icu API
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/event/{event_id}", api_key=api_key
    )

    if isinstance(result, dict) and "error" in result:
        error_message = result.get("message", "Unknown error")
        return f"Error fetching event details: {error_message}"

    # Format the response
    if not result:
        return f"No details found for event {event_id}."

    if not isinstance(result, dict):
        return f"Invalid event format for event {event_id}."

    return format_event_details(result)


@mcp.tool()
async def get_wellness_data(
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Get wellness data for an athlete from Intervals.icu

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to 30 days ago)
        end_date: End date in YYYY-MM-DD format (optional, defaults to today)
    """
    # Use provided athlete_id or fall back to global ATHLETE_ID
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."

    # Parse date parameters
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    # Call the Intervals.icu API
    params = {"oldest": start_date, "newest": end_date}

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/wellness", api_key=api_key, params=params
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching wellness data: {result.get('message')}"

    # Format the response
    if not result:
        return (
            f"No wellness data found for athlete {athlete_id_to_use} in the specified date range."
        )

    wellness_summary = "Wellness Data:\n\n"

    # Handle both list and dictionary responses
    if isinstance(result, dict):
        for date_str, data in result.items():
            # Add the date to the data dictionary if it's not already present
            if isinstance(data, dict) and "date" not in data:
                data["date"] = date_str
            wellness_summary += format_wellness_entry(data) + "\n\n"
    elif isinstance(result, list):
        for entry in result:
            if isinstance(entry, dict):
                wellness_summary += format_wellness_entry(entry) + "\n\n"

    return wellness_summary


def _resolve_workout_type(name: str | None, workout_type: str | None) -> str:
    """Determine the workout type based on the name and provided value."""
    if workout_type:
        return workout_type
    name_lower = name.lower() if name else ""
    mapping = [
        ("Ride", ["bike", "cycle", "cycling", "ride"]),
        ("Run", ["run", "running", "jog", "jogging"]),
        ("Swim", ["swim", "swimming", "pool"]),
        ("Walk", ["walk", "walking", "hike", "hiking"]),
        ("Row", ["row", "rowing"]),
    ]
    for workout, keywords in mapping:
        if any(keyword in name_lower for keyword in keywords):
            return workout
    return "Ride"  # Default


@mcp.tool()
async def delete_event(
    event_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Delete event for an athlete from Intervals.icu
    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        event_id: The Intervals.icu event ID
    """
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."
    if not event_id:
        return "Error: No event ID provided."
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events/{event_id}", api_key=api_key, method="DELETE"
    )
    if isinstance(result, dict) and "error" in result:
        return f"Error deleting event: {result.get('message')}"
    return json.dumps(result, indent=2)


@mcp.tool()
async def delete_events_by_date_range(
    start_date: str,
    end_date: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Delete events for an athlete from Intervals.icu in the specified date range.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    """
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        return "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."
    params = {"oldest": validate_date(start_date), "newest": validate_date(end_date)}
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events", api_key=api_key, params=params
    )
    if isinstance(result, dict) and "error" in result:
        return f"Error deleting events: {result.get('message')}"
    events = result if isinstance(result, list) else []
    failed_events = []
    for event in events:
        result = await make_intervals_request(
            url=f"/athlete/{athlete_id_to_use}/events/{event.get('id')}", api_key=api_key, method="DELETE"
        )
        if isinstance(result, dict) and "error" in result:
            failed_events.append(event.get('id'))
    return f"Deleted {len(events) - len(failed_events)} events. Failed to delete {len(failed_events)} events: {failed_events}"


@mcp.tool()
async def get_triathlon_workout_files(
    category: str,
    sub_category: str | None = None,
    metric: str = "HR",
    limit: int = 50,
) -> str:
    """Get triathlon workout JSON files from the local workout files collection.

    Args:
        category: The workout category (e.g., "Bike", "Run", "Swim")
        sub_category: Optional sub-category filter (e.g., "Aerobic", "Anaerobic", "Foundation", "Recovery", etc.)
        metric: The workout metric type - "HR", "Power", "Pace", or "Meters" (defaults to "HR")
        limit: Maximum number of files to return (defaults to 50)
    """
    import os

    # Validate metric
    valid_metrics = ["HR", "Power", "Pace", "Meters"]
    if metric not in valid_metrics:
        return f"Error: Invalid metric '{metric}'. Valid options are: {', '.join(valid_metrics)}"

    # Validate category
    valid_categories = ["Bike", "Run", "Swim"]
    if category not in valid_categories:
        return f"Error: Invalid category '{category}'. Valid options are: {', '.join(valid_categories)}"

    # Construct directory path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    workout_dir = os.path.join(base_dir, "triathlon_workout_files", f"80_20_{category}_{metric}_80_20_Endurance_")

    if not os.path.exists(workout_dir):
        return f"Error: Workout directory not found for {category} with {metric} metric."

    try:
        # Get all JSON files in the directory
        json_files = [f for f in os.listdir(workout_dir) if f.endswith('.json') and not f.startswith('Copyright_')]

        if not json_files:
            return f"No workout files found for {category} with {metric} metric."

        # Filter by sub-category if provided
        if sub_category:
            sub_category_lower = sub_category.lower()

            # Define sport-specific sub-category mappings based on actual file naming patterns
            sport_subcategory_patterns = {
                "Bike": {
                    "aerobic": ["CAe", "CAP"],  # Aerobic Intervals, Aerobic Progression
                    "anaerobic": ["CAI", "CAn"],  # Anaerobic Intervals
                    "accelerations": ["CA1", "CA2", "CA3", "CA4", "CA5", "CA6", "CA7", "CA8", "CA9"],
                    "cruise": ["CCI"],  # Cruise Intervals
                    "critical_power": ["CCP"],  # Critical Power
                    "depletion": ["CD"],  # Depletion
                    "descending": ["CDI"],  # Descending Intervals
                    "foundation": ["CF"],  # Foundation
                    "fast_finish": ["CFA", "CFF"],  # Fast Finish
                    "force": ["CFo"],  # Force Intervals
                    "mixed": ["CIM", "CMI"],  # Mixed Intervals
                    "sprint": ["CIR"],  # Sprint Intervals
                    "progression": ["CPI"],  # Progression Intervals
                    "power_repetitions": ["CPR"],  # Power Repetitions
                    "recovery": ["CRe"],  # Recovery
                    "speed_play": ["CSP"],  # Speed Play
                    "speed_repetitions": ["CSR"],  # Speed Repetitions
                    "steady_state": ["CSS"],  # Steady State
                    "tempo": ["CT"],  # Tempo
                    "threshold": ["CTR"],  # Threshold
                    "time_trial": ["CTT"],  # Time Trial
                    "variable_intensity": ["CVI"],  # Variable Intensity
                    "vo2max": ["CVO2M"],  # VO2 Max
                    "endurance": ["EC"],  # Endurance
                    "easy": ["EZC"],  # Easy
                    "lactate": ["LIC"],  # Lactate Intervals
                    "over_under": ["OUC"],  # Over Under Intervals
                },
                "Run": {
                    "aerobic": ["RAe"],  # Aerobic Intervals
                    "anaerobic": ["RAI", "RAn"],  # Anaerobic Intervals
                    "accelerations": ["RA"],  # Accelerations (RA0-RA9)
                    "cruise": ["RCI"],  # Cruise Intervals
                    "critical_velocity": ["RCV"],  # Critical Velocity
                    "depletion": ["RD"],  # Depletion (RD0-RD6)
                    "descending": ["RDI"],  # Descending Intervals
                    "foundation": ["RF"],  # Foundation
                    "fast_finish": ["RFF"],  # Fast Finish
                    "fartlek": ["RFR"],  # Fartlek (Run Fast Repetitions)
                    "half_marathon": ["RHM"],  # Half Marathon
                    "heart_rate": ["RHR"],  # Heart Rate Training
                    "long": ["RL"],  # Long Runs
                    "long_speedplay": ["RLS"],  # Long Speed Play
                    "mixed": ["RMI"],  # Mixed Intervals
                    "marathon_pace": ["RMP"],  # Marathon Pace
                    "progression": ["RP"],  # Progression
                    "progression_fartlek": ["RPF"],  # Progression Fartlek
                    "progression_intervals": ["RPI"],  # Progression Intervals
                    "recovery": ["RRe"],  # Recovery
                    "short_intervals": ["RSI"],  # Short Intervals
                    "speed_play": ["RSP"],  # Speed Play
                    "steady_state": ["RSS"],  # Steady State
                    "tempo": ["RT"],  # Tempo
                    "time_trial": ["RTT"],  # Time Trial
                    "variable_intensity": ["RVI"],  # Variable Intensity
                    "vo2max": ["RVO2M"],  # VO2 Max
                    "cross_training": ["RXT"],  # Cross Training
                    "5k": ["R5K"],  # 5K Training
                    "10k": ["R10K"],  # 10K Training
                    "easy": ["ER"],  # Easy Runs
                    "easy_fast_finish": ["ERFF"],  # Easy with Fast Finish
                    "long_finish": ["LFR"],  # Long Finish Runs
                    "long_intervals": ["LIR"],  # Long Intervals
                    "outdoor": ["OUR"],  # Outdoor Runs
                    "warmup": ["WR"],  # Warmup Runs
                },
                "Swim": {
                    "aerobic": ["SAe"],  # Aerobic Swimming
                    "broken_swims": ["SBB"],  # Broken Base Builds
                    "cruise": ["SCI"],  # Cruise Intervals
                    "critical_pace": ["SCP"],  # Critical Pace
                    "endurance": ["SE"],  # Endurance
                    "easy_endurance": ["SEE"],  # Easy Endurance
                    "endurance_recovery": ["SER"],  # Endurance Recovery
                    "foundation": ["SF"],  # Foundation
                    "short_intervals": ["SIS"],  # Short Intervals
                    "lactate": ["SLI"],  # Lactate Intervals
                    "mixed": ["SMI"],  # Mixed Intervals
                    "recovery": ["SRe"],  # Recovery
                    "short_sprint": ["SSI"],  # Short Sprint Intervals
                    "speed_play": ["SSP"],  # Speed Play
                    "tempo": ["ST"],  # Tempo
                    "threshold_intervals": ["STI"],  # Threshold Intervals
                    "time_trial": ["STT"],  # Time Trial
                }
            }

            # Get sub-category patterns for the specific sport
            subcategory_patterns = sport_subcategory_patterns.get(category, {})

            # Find matching patterns for the sub-category
            matching_patterns = []
            for key, patterns in subcategory_patterns.items():
                if sub_category_lower in key or key in sub_category_lower:
                    matching_patterns.extend(patterns)

            # Filter files based on matching patterns
            filtered_files = []
            if matching_patterns:
                for file in json_files:
                    if any(file.startswith(pattern) for pattern in matching_patterns):
                        filtered_files.append(file)
                json_files = filtered_files
            else:
                # No patterns matched the sub-category, return empty result
                return f"No workout files found for {category} with {metric} metric and sub-category '{sub_category}'. Available sub-categories: {', '.join(subcategory_patterns.keys())}"

            if not json_files:
                return f"No workout files found for {category} with {metric} metric and sub-category '{sub_category}'."

        # Limit results to avoid overwhelming output
        json_files = sorted(json_files)[:limit]  # Limit to specified number of files

        # Load and return the JSON files
        results = []
        for filename in json_files:
            file_path = os.path.join(workout_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    workout_data = json.load(f)

                # Extract key information for summary
                description = workout_data.get('description', 'No description available')[:200] + "..."
                duration = workout_data.get('duration', 0)
                target = workout_data.get('target', 'Unknown')

                # Format duration in minutes
                duration_minutes = duration // 60 if duration else 0

                results.append({
                    "filename": filename,
                    "description": description,
                    "duration_minutes": duration_minutes,
                    "target": target,
                    "full_data": workout_data
                })

            except Exception as e:
                results.append({
                    "filename": filename,
                    "error": f"Failed to load file: {str(e)}"
                })

        # Format response
        response = f"Found {len(results)} workout files for {category} ({metric} metric)"
        if sub_category:
            response += f" in sub-category '{sub_category}'"
        response += ":\n\n"

        for result in results:
            if "error" in result:
                response += f"❌ {result['filename']}: {result['error']}\n\n"
            else:
                response += f"📋 **{result['filename']}**\n"
                response += f"   Duration: {result['duration_minutes']} minutes\n"
                response += f"   Target: {result['target']}\n"
                response += f"   Description: {result['description']}\n\n"

        return response

    except Exception as e:
        return f"Error accessing workout files: {str(e)}"


@mcp.tool()
async def get_triathlon_workout_file_content(
    category: str,
    metric: str = "HR",
    filename: str = "",
) -> str:
    """Get the full JSON content of a specific triathlon workout file.

    Args:
        category: The workout category (e.g., "Bike", "Run", "Swim")
        metric: The workout metric type - "HR", "Power", "Pace", or "Meters" (defaults to "HR")
        filename: The exact filename of the workout file to retrieve (e.g., "SRe1_Recovery_.json")
    """
    import os
    import json

    # Validate inputs
    valid_metrics = ["HR", "Power", "Pace", "Meters"]
    if metric not in valid_metrics:
        return f"Error: Invalid metric '{metric}'. Valid options are: {', '.join(valid_metrics)}"

    valid_categories = ["Bike", "Run", "Swim"]
    if category not in valid_categories:
        return f"Error: Invalid category '{category}'. Valid options are: {', '.join(valid_categories)}"

    if not filename:
        return "Error: filename parameter is required"

    if not filename.endswith('.json'):
        filename += '.json'

    # Construct directory path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    workout_dir = os.path.join(base_dir, "triathlon_workout_files", f"80_20_{category}_{metric}_80_20_Endurance_")

    if not os.path.exists(workout_dir):
        return f"Error: Workout directory not found for {category} with {metric} metric."

    # Construct full file path
    file_path = os.path.join(workout_dir, filename)

    if not os.path.exists(file_path):
        return f"Error: Workout file '{filename}' not found in {category} ({metric}) directory."

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            workout_data = json.load(f)

        # Return the full JSON content in a formatted way
        return json.dumps(workout_data, indent=2, ensure_ascii=False)

    except Exception as e:
        return f"Error reading workout file '{filename}': {str(e)}"


@mcp.tool()
async def parse_triathlon_workout_to_readable_format(
    category: str,
    metric: str = "HR",
    filename: str = "",
) -> str:
    """Parse a triathlon workout JSON file into a readable, formatted text suitable for Claude.

    Args:
        category: The workout category (e.g., "Bike", "Run", "Swim")
        metric: The workout metric type - "HR", "Power", "Pace", or "Meters" (defaults to "HR")
        filename: The exact filename of the workout file to parse (e.g., "SRe1_Recovery_.json")
    """
    import os
    import json
    import math

    # Validate inputs
    valid_metrics = ["HR", "Power", "Pace", "Meters"]
    if metric not in valid_metrics:
        return f"Error: Invalid metric '{metric}'. Valid options are: {', '.join(valid_metrics)}"

    valid_categories = ["Bike", "Run", "Swim"]
    if category not in valid_categories:
        return f"Error: Invalid category '{category}'. Valid options are: {', '.join(valid_categories)}"

    if not filename:
        return "Error: filename parameter is required"

    if not filename.endswith('.json'):
        filename += '.json'

    # Get the workout data
    base_dir = os.path.dirname(os.path.abspath(__file__))
    workout_dir = os.path.join(base_dir, "triathlon_workout_files", f"80_20_{category}_{metric}_80_20_Endurance_")
    file_path = os.path.join(workout_dir, filename)

    if not os.path.exists(file_path):
        return f"Error: Workout file '{filename}' not found in {category} ({metric}) directory."

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            workout_data = json.load(f)

        # Helper functions
        def format_duration(seconds):
            """Convert seconds to readable format (m/s/h)"""
            if seconds < 60:
                return f"{seconds}s"
            elif seconds < 3600:
                minutes = seconds // 60
                remaining_seconds = seconds % 60
                if remaining_seconds == 0:
                    return f"{minutes}m"
                else:
                    return f"{minutes}m{remaining_seconds}s"
            else:
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                if minutes == 0:
                    return f"{hours}h"
                else:
                    return f"{hours}h{minutes}m"

        def format_total_duration(seconds):
            """Format total duration in HH:MM format"""
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if hours == 0:
                return f"{minutes}m"
            else:
                return f"{hours:02d}:{minutes:02d}"

        def format_power_zone(power_data):
            """Format power zone as % FTP"""
            if not power_data:
                return ""
            start = power_data.get('start', 0)
            end = power_data.get('end', 0)
            if start == end:
                return f"{start}% FTP"
            else:
                return f"{start}-{end}% FTP"

        def format_hr_zone(hr_data):
            """Format HR zone as % LTHR"""
            if not hr_data:
                return ""
            start = hr_data.get('start', 0)
            end = hr_data.get('end', 0)
            if start == end:
                return f"{start}% LTHR"
            else:
                return f"{start}-{end}% LTHR"

        def format_pace_zone(pace_data):
            """Format pace zone as % threshold pace"""
            if not pace_data:
                return ""
            start = pace_data.get('start', 0)
            end = pace_data.get('end', 0)
            if start == end:
                return f"{start}% pace"
            else:
                return f"{start}-{end}% pace"

        def get_workout_type():
            """Determine workout type from category"""
            type_mapping = {
                "Bike": "Ride",
                "Run": "Run", 
                "Swim": "Swim"
            }
            return type_mapping.get(category, category)

        def format_distance(distance):
            """Format distance for swim workouts"""
            if distance and distance > 0:
                return f"{int(distance)} meter"
            return ""

        def parse_step(step, is_swim=False):
            """Parse a single step/interval"""
            text = step.get('text', 'Active')
            duration = step.get('duration', 0)
            distance = step.get('distance', 0)
            
            # Format instruction text
            instruction = text if text != 'Active' else 'Maintain effort'
            
            # Format duration or distance
            if is_swim and distance:
                duration_str = format_distance(distance)
            else:
                duration_str = format_duration(duration)
            
            # Format intensity zones
            intensity = ""
            if 'power' in step:
                intensity = format_power_zone(step['power'])
            elif 'hr' in step:
                intensity = format_hr_zone(step['hr'])
            elif 'pace' in step:
                intensity = format_pace_zone(step['pace'])
            
            return f'- "{instruction}" {duration_str} {intensity}'.strip()

        # Start building the formatted output
        result = []
        
        # Extract workout name from filename
        workout_name = filename.replace('.json', '').replace('_', ' ')
        result.append(f"Workout Name: {workout_name}")
        result.append("")
        
        # Workout type
        result.append(f"Workout Type: {get_workout_type()}")
        result.append("")
        
        # Total duration
        total_duration = workout_data.get('duration', 0)
        result.append(f"Total Duration: {format_total_duration(total_duration)}")
        result.append("")
        
        # Description
        description = workout_data.get('description', 'No description available')
        # Clean up description text - remove markdown-breaking patterns
        cleaned_description = description.strip()
        cleaned_description = cleaned_description.replace('`- - - -', '----')
        cleaned_description = cleaned_description.replace('- - - -', '----')
        cleaned_description = cleaned_description.replace('`', '')  # Remove backticks that could break formatting
        
        result.append("Description:")
        result.append("```")
        result.append(cleaned_description)
        result.append("```")
        result.append("")
        
        # Parse steps/intervals
        steps = workout_data.get('steps', [])
        is_swim = (category == "Swim")
        
        if steps:
            result.append("```")
            
            for i, step in enumerate(steps):
                reps = step.get('reps', 0)
                
                if reps > 1:
                    # Repeated intervals
                    result.append(f"Repeat {reps}x")
                    sub_steps = step.get('steps', [])
                    if sub_steps:
                        for sub_step in sub_steps:
                            interval_line = parse_step(sub_step, is_swim)
                            result.append(interval_line)
                    else:
                        # Single step with reps
                        interval_line = parse_step(step, is_swim)
                        result.append(interval_line)
                    result.append("")
                else:
                    # Single interval
                    text = step.get('text', 'Active')
                    interval_name = text if text != 'Active' else f"Interval {i+1}"
                    
                    # Check if this step has sub-steps
                    sub_steps = step.get('steps', [])
                    if sub_steps:
                        result.append(interval_name)
                        for sub_step in sub_steps:
                            interval_line = parse_step(sub_step, is_swim)
                            result.append(interval_line)
                        result.append("")
                    else:
                        result.append(interval_name)
                        interval_line = parse_step(step, is_swim)
                        result.append(interval_line)
                        result.append("")
            
            result.append("```")
        
        return '\n'.join(result)

    except Exception as e:
        return f"Error parsing workout file '{filename}': {str(e)}"


@mcp.tool()
async def add_or_update_event(
    workout_type: str,
    name: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    event_id: str | None = None,
    start_date: str | None = None,
    workout_doc: WorkoutDoc | None = None,
    moving_time: int | None = None,
    distance: int | None = None,
) -> str:
    """Post event for an athlete to Intervals.icu this follows the event api from intervals.icu
    If event_id is provided, the event will be updated instead of created.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        event_id: The Intervals.icu event ID (optional, will use event_id from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to today)
        name: Name of the activity
        workout_doc: steps as a list of Step objects (optional, but necessary to define workout steps)
        workout_type: Workout type (e.g. Ride, Run, Swim, Walk, Row)
        moving_time: Total expected moving time of the workout in seconds (optional)
        distance: Total expected distance of the workout in meters (optional)

    Example:
        "workout_doc": {
            "description": "High-intensity workout for increasing VO2 max",
            "steps": [
                {"power": {"value": "80", "units": "%ftp"}, "duration": "900", "warmup": true},
                {"reps": 2, "text": "High-intensity intervals", "steps": [
                    {"power": {"value": "110", "units": "%ftp"}, "distance": "500", "text": "High-intensity"},
                    {"power": {"value": "80", "units": "%ftp"}, "duration": "90", "text": "Recovery"}
                ]},
                {"power": {"value": "80", "units": "%ftp"}, "duration": "600", "cooldown": true}
                {"text": ""}, # Add comments or blank lines for readability
            ]
        }

    Step properties:
        distance: Distance of step in meters
            {"distance": "5000"}
        duration: Duration of step in seconds
            {"duration": "1800"}
        power/hr/pace/cadence: Define step intensity
            Percentage of FTP: {"power": {"value": "80", "units": "%ftp"}}
            Absolute power: {"power": {"value": "200", "units": "w"}}
            Heart rate: {"hr": {"value": "75", "units": "%hr"}}
            Heart rate (LTHR): {"hr": {"value": "85", "units": "%lthr"}}
            Cadence: {"cadence": {"value": "90", "units": "rpm"}}
            Pace by ftp: {"pace": {"value": "80", "units": "%pace"}}
            Pace by zone: {"pace": {"value": "Z2", "units": "pace_zone"}}
            Zone by power: {"power": {"value": "Z2", "units": "power_zone"}}
            Zone by heart rate: {"hr": {"value": "Z2", "units": "hr_zone"}}
        Ranges: Specify ranges for power, heart rate, or cadence:
            {"power": {"start": "80", "end": "90", "units": "%ftp"}}
        Ramps: Instead of a range, indicate a gradual change in intensity (useful for ERG workouts):
            {"ramp": True, "power": {"start": "80", "end": "90", "units": "%ftp"}}
        Repeats: include the reps property and add nested steps
            {"reps": 3,
            "steps": [
                {"power": {"value": "110", "units": "%ftp"}, "distance": "500", "text": "High-intensity"},
                {"power": {"value": "80", "units": "%ftp"}, "duration": "90", "text": "Recovery"}
            ]}
        Free Ride: Include free to indicate a segment without ERG control, optionally with a suggested power range:
            {"free": true, "power": {"value": "80", "units": "%ftp"}}
        Comments and Labels: Add descriptive text to label steps:
            {"text": "Warmup"}

    How to use steps:
        - Set distance or duration as appropriate for step
        - Use "reps" with nested steps to define repeat intervals (as in example above)
        - Define one of "power", "hr" or "pace" to define step intensity
    """
    message = None
    athlete_id_to_use = athlete_id if athlete_id is not None else ATHLETE_ID
    if not athlete_id_to_use:
        message = "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables."
    else:
        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")
        try:
            resolved_workout_type = _resolve_workout_type(name, workout_type)
            data = {
                "start_date_local": start_date + "T00:00:00",
                "category": "WORKOUT",
                "name": name,
                "description": str(workout_doc) if workout_doc else None,
                "type": resolved_workout_type,
                "moving_time": moving_time,
                "distance": distance,
            }
            result = await make_intervals_request(
                url=f"/athlete/{athlete_id_to_use}/events" +("/"+event_id if event_id else ""),
                api_key=api_key,
                data=data,
                method="PUT" if event_id else "POST",
            )
            action = "updated" if event_id else "created"
            if isinstance(result, dict) and "error" in result:
                error_message = result.get("message", "Unknown error")
                message = f"Error {action} event: {error_message}, data used: {data}"
            elif not result:
                message = f"No events {action} for athlete {athlete_id_to_use}."
            elif isinstance(result, dict):
                message = f"Successfully {action} event: {json.dumps(result, indent=2)}"
            else:
                message = f"Event {action} successfully at {start_date}"
        except ValueError as e:
            message = f"Error: {e}"
    return message


# Run the server
if __name__ == "__main__":
    mcp.run()
