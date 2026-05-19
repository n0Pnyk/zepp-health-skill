"""Configuration loading and authentication management.

Supports multiple configuration sources, priority from high to low:
1. CLI arguments (--token, --user-id, --cookie)
2. File specified via --config or $ZEPP_CONFIG environment variable
3. ./config.json
4. ~/.config/zepp-health/config.json
5. Environment variables ZEPP_APP_TOKEN, ZEPP_USER_ID, etc.
6. ZEPP_COOKIE environment variable (auto-parsed)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# Default host for China region
DEFAULT_HOST = "api-mifit-cn3.zepp.com"

# Mapping of config fields to environment variables
ENV_MAP = {
    "app_token": "ZEPP_APP_TOKEN",
    "user_id": "ZEPP_USER_ID",
    "host": "ZEPP_HOST",
    "timezone": "ZEPP_TIMEZONE",
    "app_platform": "ZEPP_APP_PLATFORM",
    "lang": "ZEPP_LANG",
    "country": "ZEPP_COUNTRY",
    "cookie": "ZEPP_COOKIE",
}

# Region to host mapping
REGION_HOSTS = {
    "1": "api-mifit-cn3.zepp.com",     # China
    "2": "api-mifit-us3.zepp.com",     # United States
    "3": "api-mifit-eu3.zepp.com",     # Europe
    "4": "api-mifit-sg3.zepp.com",     # Singapore
}


class AppConfig(BaseModel):
    """Application configuration."""

    app_token: str = ""
    user_id: str = ""
    host: str = DEFAULT_HOST
    timezone: str = "Asia/Shanghai"
    app_platform: str = "ios_phone"
    lang: str = "zh"
    country: str = "CN"
    region: str = "1"


def parse_cookie(cookie_str: str) -> dict[str, str]:
    """Parse configuration fields from a cookie string.

    Supported format: "userid=xxx; apptoken=xxx; region=1"
    """
    result: dict[str, str] = {}
    if not cookie_str:
        return result

    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip()
        value = value.strip()

        # Map cookie field names to config field names
        if key == "userid":
            result["user_id"] = value
        elif key == "apptoken":
            result["app_token"] = value
        elif key == "region":
            result["region"] = value
            # Infer host from region
            if value in REGION_HOSTS:
                result["host"] = REGION_HOSTS[value]

    return result


def _config_search_paths(config_path: str | None = None) -> list[Path]:
    """Return config file search paths in priority order."""
    paths: list[Path] = []

    # CLI-specified path takes priority
    if config_path:
        paths.append(Path(config_path).expanduser())

    # Environment variable
    env_path = os.environ.get("ZEPP_CONFIG", "").strip()
    if env_path:
        paths.append(Path(env_path).expanduser())

    # Package directory (skill root / project root)
    _package_dir = Path(__file__).resolve().parent.parent
    if _package_dir.is_dir():
        paths.append(_package_dir / "config.json")

    # CLI project fallback (shared config)
    _cli_config = Path.home() / "projects" / "zepp-health" / "config.json"
    if _cli_config.is_file():
        paths.append(_cli_config)

    # Current directory
    paths.append(Path.cwd() / "config.json")

    # User config directory
    paths.append(Path.home() / ".config" / "zepp-health" / "config.json")

    # Deduplicate
    seen: set[Path] = set()
    result: list[Path] = []
    for p in paths:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            result.append(p)

    return result


def load_config(
    config_path: str | None = None,
    cookie: str | None = None,
    token: str | None = None,
    user_id: str | None = None,
    host: str | None = None,
) -> AppConfig:
    """Load configuration, merging multiple sources by priority.

    Priority (high to low):
    1. CLI arguments (token, user_id, host)
    2. cookie parameter
    3. Config file
    4. Environment variables
    """
    data: dict[str, Any] = {}

    # 1. Load from config file
    for p in _config_search_paths(config_path):
        if p.is_file():
            try:
                data = json.loads(p.read_text())
                data["_loaded_from"] = str(p)
            except json.JSONDecodeError:
                continue
            break

    # 2. Environment variable overrides (including ZEPP_COOKIE)
    for field_name, env_name in ENV_MAP.items():
        v = os.environ.get(env_name, "").strip()
        if v:
            data[field_name] = v

    # 3. Cookie parameter overrides
    if cookie:
        cookie_data = parse_cookie(cookie)
        data.update(cookie_data)

    # 4. CLI arguments have highest priority
    if token:
        data["app_token"] = token
    if user_id:
        data["user_id"] = user_id
    if host:
        data["host"] = host

    # If there is a cookie field but it hasn't been explicitly parsed, parse it
    if "cookie" in data and not data.get("app_token"):
        cookie_data = parse_cookie(data.pop("cookie"))
        # Parsed cookie values have lower priority than explicit config
        for k, v in cookie_data.items():
            if k not in data or not data[k]:
                data[k] = v
    else:
        data.pop("cookie", None)

    # Clean up non-config fields
    data.pop("_loaded_from", None)

    # Set default host
    if not data.get("host"):
        region = data.get("region", "1")
        data["host"] = REGION_HOSTS.get(region, DEFAULT_HOST)

    return AppConfig(**{k: v for k, v in data.items() if k in AppConfig.model_fields})


def save_config(data: dict[str, Any], path: Path) -> Path:
    """Save configuration to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: v for k, v in data.items() if k in AppConfig.model_fields and v}
    path.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path
