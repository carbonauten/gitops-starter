import hashlib
import os
from typing import Optional, Tuple


DEFAULT_PERCENT_A = 50.0


def _clamp_percentage(value: float) -> float:
    return max(0.0, min(100.0, value))


def assign_variant(user_id: str, percent_a: Optional[float] = None) -> str:
    """
    Deterministically assign a user to variant A or B based on their user_id.

    The percentage of users routed to A is controlled by:
    - percent_a argument if provided, otherwise
    - AB_PIPELINE_A_PERCENT env var (default 50.0)
    """
    if percent_a is None:
        try:
            percent_a = float(os.getenv("AB_PIPELINE_A_PERCENT", str(DEFAULT_PERCENT_A)))
        except ValueError:
            percent_a = DEFAULT_PERCENT_A

    percent_a = _clamp_percentage(percent_a)

    # Stable hash -> bucket in [0, 99]
    h = int(hashlib.sha256(user_id.encode("utf-8")).hexdigest(), 16)
    bucket = h % 100
    return "A" if bucket < percent_a else "B"


def resolve_topic(
    user_id: str,
    base_topic: str = "events.v1",
    percent_a: Optional[float] = None,
) -> Tuple[str, str]:
    """
    Return the Kafka topic and variant for a given user_id.

    Example:
      topic, variant = resolve_topic("user-123")
      # topic -> "events.v1.control" or "events.v1.experiment"
      # variant -> "A" or "B"
    """
    variant = assign_variant(user_id, percent_a=percent_a)
    suffix = "control" if variant == "A" else "experiment"
    return f"{base_topic}.{suffix}", variant

