"""Zepp Health data analysis toolkit.

Fetches health data via the Zepp/Amazfit API, performs normalization and health score analysis.
"""

__version__ = "0.2.0"

from zepp_health.client import ZeppClient
from zepp_health.config import AppConfig, load_config, parse_cookie
from zepp_health.models import HealthReport

__all__ = [
    "ZeppClient",
    "AppConfig",
    "load_config",
    "parse_cookie",
    "HealthReport",
]
