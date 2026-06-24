from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

RESOURCE_TYPES: tuple[str, ...] = ("video", "course", "book", "project")

DEFAULT_SESSION_MINUTES: dict[str, int] = {
    "video": 45,
    "course": 60,
    "book": 50,
    "project": 90,
}

DEFAULT_WEIGHTS: dict[str, float] = {
    "video": 0.5,
    "course": 0.2,
    "book": 0.1,
    "project": 0.2,
}

# Higher rank wins. Anything not listed (including ``None`` / unknown) falls
# back to ``URGENCY_DEFAULT_RANK`` so it sorts behind all explicit urgencies.
URGENCY_RANK: dict[str, int] = {
    "Critical": 3,
    "High": 2,
    "Medium": 1,
}
URGENCY_DEFAULT_RANK: int = 0

DEFAULT_MAX_SESSIONS_PER_DAY: int = 2
DEFAULT_GAP_MINUTES: int = 10

_DAYS_PER_WEEK: int = 7
_MINUTES_PER_HOUR: int = 60
_UID_PREFIX: str = "pf"


class ScheduleError(ValueError):
    """Raised when scheduling inputs are invalid."""


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------


def _require_zone(timezone_name: str) -> ZoneInfo:
    if not isinstance(timezone_name, str) or not timezone_name.strip():
        raise ScheduleError("timezone must be a non-empty IANA string")
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ScheduleError(f"unknown timezone: {timezone_name!r}") from exc


def _parse_anchor_date(start_date: str) -> date:
    if not isinstance(start_date, str):
        raise ScheduleError("start_date must be a 'YYYY-MM-DD' string")
    try:
        return date.fromisoformat(start_date)
    except ValueError as exc:
        raise ScheduleError(f"start_date must be 'YYYY-MM-DD', got {start_date!r}") from exc


def _parse_hhmm(value: object, field: str) -> time:
    if not isinstance(value, str):
        raise ScheduleError(f"{field} must be an 'HH:MM' string, got {value!r}")
    parts = value.split(":")
    if len(parts) != 2:
        raise ScheduleError(f"{field} must be 'HH:MM', got {value!r}")
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ScheduleError(f"{field} must be 'HH:MM', got {value!r}") from exc
    if not (0 <= hour <= 23) or not (0 <= minute <= 59):
        raise ScheduleError(f"{field} must be a valid 24h time, got {value!r}")
    return time(hour=hour, minute=minute)


def _validate_availability(availability: list[dict]) -> list[dict]:
    """Return a normalized, validated copy of the availability rows."""
    if not isinstance(availability, list) or not availability:
        raise ScheduleError("availability must be a non-empty list of slot rows")

    normalized: list[dict] = []
    for index, row in enumerate(availability):
        if not isinstance(row, dict):
            raise ScheduleError(f"availability[{index}] must be a dict")
        weekday = row.get("weekday")
        if not isinstance(weekday, int) or isinstance(weekday, bool):
            raise ScheduleError(f"availability[{index}].weekday must be an int 0-6")
        if not (0 <= weekday <= _DAYS_PER_WEEK - 1):
            raise ScheduleError(f"availability[{index}].weekday must be 0-6, got {weekday}")
        start = _parse_hhmm(row.get("start"), f"availability[{index}].start")
        end = _parse_hhmm(row.get("end"), f"availability[{index}].end")
        if start >= end:
            raise ScheduleError(
                f"availability[{index}] start ({row.get('start')}) must be before end ({row.get('end')})"
            )
        normalized.append({"weekday": weekday, "start": start, "end": end})
    return normalized


def _validate_horizon(horizon_days: object) -> int:
    if not isinstance(horizon_days, int) or isinstance(horizon_days, bool):
        raise ScheduleError("horizon_days must be a positive integer")
    if horizon_days <= 0:
        raise ScheduleError(f"horizon_days must be > 0, got {horizon_days}")
    return horizon_days


# ---------------------------------------------------------------------------
# Slot expansion
# ---------------------------------------------------------------------------


def _expand_slots(
    *,
    anchor: date,
    horizon_days: int,
    zone: ZoneInfo,
    availability: list[dict],
) -> list[dict]:
    """Expand weekly availability into concrete dated, tz-aware slots.

    Days are iterated in order; for each day every availability row whose
    weekday matches is emitted in input order. The result is therefore already
    sorted chronologically.
    """
    rows_by_weekday: dict[int, list[dict]] = {}
    for row in availability:
        rows_by_weekday.setdefault(row["weekday"], []).append(row)

    slots: list[dict] = []
    for offset in range(horizon_days):
        current = anchor + timedelta(days=offset)
        for row in rows_by_weekday.get(current.weekday(), []):
            local_start = datetime.combine(current, row["start"], tzinfo=zone)
            local_end = datetime.combine(current, row["end"], tzinfo=zone)
            slots.append(
                {
                    "date": current,
                    "local_start_dt": local_start,
                    "local_end_dt": local_end,
                    "week_index": offset // _DAYS_PER_WEEK,
                }
            )
    return slots


# ---------------------------------------------------------------------------
# Resource queues + skill priority
# ---------------------------------------------------------------------------


def _skill_priority_index(skills: list[dict] | None) -> dict[str, tuple[int, int]]:
    """Map a skill name -> (urgency_rank, demand) for stable priority sorting."""
    if not skills:
        return {}
    index: dict[str, tuple[int, int]] = {}
    for entry in skills:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue
        urgency = entry.get("urgency")
        rank = URGENCY_RANK.get(urgency, URGENCY_DEFAULT_RANK)
        demand = entry.get("demand")
        demand_value = demand if isinstance(demand, int) and not isinstance(demand, bool) else 0
        index[name] = (rank, demand_value)
    return index


def _normalize_resource(raw: dict, index: int) -> dict:
    if not isinstance(raw, dict):
        raise ScheduleError(f"resources[{index}] must be a dict")
    resource_type = raw.get("type")
    if resource_type not in RESOURCE_TYPES:
        raise ScheduleError(
            f"resources[{index}].type must be one of {RESOURCE_TYPES}, got {resource_type!r}"
        )
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ScheduleError(f"resources[{index}].title must be a non-empty string")
    url = raw.get("url")
    if url is not None and not isinstance(url, str):
        raise ScheduleError(f"resources[{index}].url must be a string or None")
    skill = raw.get("skill")
    if skill is not None and not isinstance(skill, str):
        raise ScheduleError(f"resources[{index}].skill must be a string or None")
    return {
        "type": resource_type,
        "title": title,
        "url": url,
        "skill": skill or "",
        "input_order": index,
    }


def _build_queues(
    resources: list[dict],
    priority: dict[str, tuple[int, int]],
) -> dict[str, list[dict]]:
    """Build per-type FIFO queues, stable-sorted by skill priority.

    Input order is preserved as the final tie-breaker so the sort is fully
    deterministic. Higher-priority skills (Critical > High > Medium > unknown,
    then higher demand) are placed at the front of their type's queue.
    """
    if not isinstance(resources, list):
        raise ScheduleError("resources must be a list")

    normalized = [_normalize_resource(raw, index) for index, raw in enumerate(resources)]

    def sort_key(resource: dict) -> tuple[int, int, int]:
        rank, demand = priority.get(resource["skill"], (URGENCY_DEFAULT_RANK, 0))
        # Negate priority components so higher rank/demand sort first while the
        # input order keeps its natural ascending tie-break.
        return (-rank, -demand, resource["input_order"])

    ordered = sorted(normalized, key=sort_key)

    queues: dict[str, list[dict]] = {resource_type: [] for resource_type in RESOURCE_TYPES}
    for resource in ordered:
        queues[resource["type"]].append(resource)
    return queues


# ---------------------------------------------------------------------------
# Weighted round-robin type ordering
# ---------------------------------------------------------------------------


def _resolve_weights(preferences: dict) -> dict[str, float]:
    weights = preferences.get("weights")
    if weights is None:
        return dict(DEFAULT_WEIGHTS)
    if not isinstance(weights, dict):
        raise ScheduleError("preferences.weights must be a dict")
    resolved: dict[str, float] = {}
    for resource_type in RESOURCE_TYPES:
        value = weights.get(resource_type, 0)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ScheduleError(f"preferences.weights[{resource_type}] must be a number")
        if value < 0:
            raise ScheduleError(f"preferences.weights[{resource_type}] must be >= 0")
        resolved[resource_type] = float(value)
    return resolved


def _pick_pattern(active_weights: dict[str, float]) -> list[str]:
    """Turn relative weights into an integer pick-pattern via largest remainder.

    Returns an ordered list of resource types whose multiplicities approximate
    the target ratio. Types are considered in ``RESOURCE_TYPES`` order so the
    output is deterministic. Each cycle places ``round(sum(weights))`` picks
    (at least ``len(active)``), distributed by the largest-remainder method.
    """
    active = {rt: w for rt, w in active_weights.items() if w > 0}
    if not active:
        return []

    total_weight = sum(active.values())
    # Scale so the smallest positive weight maps to roughly one pick, keeping
    # the per-cycle pattern compact but proportional.
    smallest = min(active.values())
    target_total = max(len(active), round(total_weight / smallest))

    raw = {rt: (w / total_weight) * target_total for rt, w in active.items()}
    floors = {rt: int(math.floor(value)) for rt, value in raw.items()}
    assigned = sum(floors.values())
    remainder = target_total - assigned

    # Distribute the remaining picks to the largest fractional remainders,
    # tie-broken by RESOURCE_TYPES order for determinism.
    ordered_types = [rt for rt in RESOURCE_TYPES if rt in active]
    by_remainder = sorted(
        ordered_types,
        key=lambda rt: (-(raw[rt] - floors[rt]), RESOURCE_TYPES.index(rt)),
    )
    counts = dict(floors)
    for rt in by_remainder[:remainder]:
        counts[rt] += 1

    # Guarantee every active type appears at least once per cycle.
    for rt in ordered_types:
        if counts[rt] == 0:
            counts[rt] = 1

    pattern: list[str] = []
    for rt in ordered_types:
        pattern.extend([rt] * counts[rt])
    return pattern


def _weighted_pattern(weights: dict[str, float]) -> list[str]:
    """The full weighted-round-robin pattern over every type with weight > 0."""
    active_weights = {rt: weights[rt] for rt in RESOURCE_TYPES if weights.get(rt, 0) > 0}
    return _pick_pattern(active_weights)


def _next_type(
    queues: dict[str, list[dict]],
    pattern: list[str],
    cursor: int,
) -> tuple[str | None, int]:
    """Advance the round-robin cursor to the next servable type.

    Walks the (fixed) weighted pattern cyclically starting at ``cursor``,
    skipping types whose queues are empty so an exhausted type drops out of the
    rotation while the others keep their proportional share. Returns the chosen
    type (or ``None`` if no weighted type has resources left) and the cursor
    position to resume from on the next call.
    """
    if not pattern:
        return None, cursor
    length = len(pattern)
    for step in range(length):
        position = (cursor + step) % length
        resource_type = pattern[position]
        if queues[resource_type]:
            return resource_type, (position + 1) % length
    return None, cursor


# ---------------------------------------------------------------------------
# Session timing helpers
# ---------------------------------------------------------------------------


def _resolve_session_minutes(preferences: dict) -> dict[str, int]:
    overrides = preferences.get("session_minutes")
    resolved = dict(DEFAULT_SESSION_MINUTES)
    if overrides is None:
        return resolved
    if not isinstance(overrides, dict):
        raise ScheduleError("preferences.session_minutes must be a dict")
    for resource_type in RESOURCE_TYPES:
        if resource_type not in overrides:
            continue
        value = overrides[resource_type]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ScheduleError(
                f"preferences.session_minutes[{resource_type}] must be a positive int"
            )
        resolved[resource_type] = value
    return resolved


def _resolve_positive_int(preferences: dict, key: str, default: int) -> int:
    value = preferences.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ScheduleError(f"preferences.{key} must be a positive int")
    return value


def _resolve_gap_minutes(preferences: dict) -> int:
    value = preferences.get("gap_minutes", DEFAULT_GAP_MINUTES)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ScheduleError("preferences.gap_minutes must be an int >= 0")
    return value


# ---------------------------------------------------------------------------
# Session emission
# ---------------------------------------------------------------------------


def _make_session(
    *,
    resource: dict,
    slot: dict,
    session_start: datetime,
    session_end: datetime,
    global_index: int,
) -> dict:
    skill = resource["skill"]
    title = resource["title"]
    resource_type = resource["type"]
    goal = f"Study {title} ({resource_type}) for {skill}".strip()
    if not skill:
        goal = f"Study {title} ({resource_type})"
    return {
        "uid": f"{_UID_PREFIX}-{slot['week_index']}-{global_index}",
        "date": slot["date"].isoformat(),
        "start_utc": session_start.astimezone(timezone.utc).isoformat(),
        "end_utc": session_end.astimezone(timezone.utc).isoformat(),
        "resource_title": title,
        "resource_url": resource["url"],
        "resource_type": resource_type,
        "skill": skill,
        "week_index": slot["week_index"],
        "goal": goal,
    }


def _fill_slots(
    *,
    slots: list[dict],
    queues: dict[str, list[dict]],
    weights: dict[str, float],
    session_minutes: dict[str, int],
    max_sessions_per_day: int,
    gap_minutes: int,
) -> list[dict]:
    sessions: list[dict] = []
    sessions_by_date: dict[date, int] = {}
    gap = timedelta(minutes=gap_minutes)
    global_index = 0
    pattern = _weighted_pattern(weights)
    rotation = 0  # persistent round-robin cursor across slots and days

    for slot in slots:
        slot_date = slot["date"]
        cursor = slot["local_start_dt"]
        slot_end = slot["local_end_dt"]

        while sessions_by_date.get(slot_date, 0) < max_sessions_per_day:
            resource_type, next_rotation = _next_type(queues, pattern, rotation)
            if resource_type is None:
                return sessions  # all weighted queues exhausted

            resource = queues[resource_type][0]  # peek; pop only once it fits
            duration = timedelta(minutes=session_minutes[resource_type])
            session_end = cursor + duration
            if session_end > slot_end:
                break  # remaining time in this slot can't fit the next session

            queues[resource_type].pop(0)  # commit the pop
            rotation = next_rotation  # advance only on a committed placement
            sessions.append(
                _make_session(
                    resource=resource,
                    slot=slot,
                    session_start=cursor,
                    session_end=session_end,
                    global_index=global_index,
                )
            )
            global_index += 1
            sessions_by_date[slot_date] = sessions_by_date.get(slot_date, 0) + 1
            cursor = session_end + gap

    return sessions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_schedule(
    *,
    horizon_days: int,
    start_date: str,
    timezone: str,
    availability: list[dict],
    preferences: dict,
    resources: list[dict],
    skills: list[dict] | None = None,
) -> list[dict]:
    """Generate a deterministic study schedule.

    The engine is pure: the caller supplies ``start_date`` as the anchor; no
    wall-clock time is read. See the module docstring/constants for tunable
    defaults. Returns a list of session dicts ordered by ``start_utc`` ascending.
    Returns ``[]`` when there are no resources or no concrete slots. Raises
    :class:`ScheduleError` on invalid input.
    """
    horizon = _validate_horizon(horizon_days)
    anchor = _parse_anchor_date(start_date)
    zone = _require_zone(timezone)
    normalized_availability = _validate_availability(availability)

    if preferences is None:
        preferences = {}
    if not isinstance(preferences, dict):
        raise ScheduleError("preferences must be a dict")

    weights = _resolve_weights(preferences)
    session_minutes = _resolve_session_minutes(preferences)
    max_sessions_per_day = _resolve_positive_int(
        preferences, "max_sessions_per_day", DEFAULT_MAX_SESSIONS_PER_DAY
    )
    gap_minutes = _resolve_gap_minutes(preferences)

    priority = _skill_priority_index(skills)
    queues = _build_queues(resources, priority)

    total_resources = sum(len(queue) for queue in queues.values())
    if total_resources == 0:
        return []

    slots = _expand_slots(
        anchor=anchor,
        horizon_days=horizon,
        zone=zone,
        availability=normalized_availability,
    )
    if not slots:
        return []

    sessions = _fill_slots(
        slots=slots,
        queues=queues,
        weights=weights,
        session_minutes=session_minutes,
        max_sessions_per_day=max_sessions_per_day,
        gap_minutes=gap_minutes,
    )

    return sorted(sessions, key=lambda session: session["start_utc"])
