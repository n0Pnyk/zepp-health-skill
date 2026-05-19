"""配置加载和认证管理。

支持多种配置来源，优先级从高到低：
1. CLI 参数（--token, --user-id, --cookie）
2. --config 指定的文件 或 $ZEPP_CONFIG 环境变量
3. ./config.json
4. ~/.config/zepp-health/config.json
5. 环境变量 ZEPP_APP_TOKEN, ZEPP_USER_ID 等
6. ZEPP_COOKIE 环境变量（自动解析）
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# 中国区默认 host
DEFAULT_HOST = "api-mifit-cn3.zepp.com"

# 配置字段与环境变量的映射
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

# region 到 host 的映射
REGION_HOSTS = {
    "1": "api-mifit-cn3.zepp.com",     # 中国
    "2": "api-mifit-us3.zepp.com",     # 美国
    "3": "api-mifit-eu3.zepp.com",     # 欧洲
    "4": "api-mifit-sg3.zepp.com",     # 新加坡
}


class AppConfig(BaseModel):
    """应用配置。"""

    app_token: str = ""
    user_id: str = ""
    host: str = DEFAULT_HOST
    timezone: str = "Asia/Shanghai"
    app_platform: str = "ios_phone"
    lang: str = "zh"
    country: str = "CN"
    region: str = "1"


def parse_cookie(cookie_str: str) -> dict[str, str]:
    """从 cookie 字符串中解析配置字段。

    支持格式: "userid=xxx; apptoken=xxx; region=1"
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

        # 映射 cookie 字段名到配置字段名
        if key == "userid":
            result["user_id"] = value
        elif key == "apptoken":
            result["app_token"] = value
        elif key == "region":
            result["region"] = value
            # 根据 region 推断 host
            if value in REGION_HOSTS:
                result["host"] = REGION_HOSTS[value]

    return result


def _config_search_paths(config_path: str | None = None) -> list[Path]:
    """按优先级返回配置文件搜索路径。"""
    paths: list[Path] = []

    # CLI 指定的路径优先
    if config_path:
        paths.append(Path(config_path).expanduser())

    # 环境变量
    env_path = os.environ.get("ZEPP_CONFIG", "").strip()
    if env_path:
        paths.append(Path(env_path).expanduser())

    # 当前目录
    paths.append(Path.cwd() / "config.json")

    # 用户配置目录
    paths.append(Path.home() / ".config" / "zepp-health" / "config.json")

    # 去重
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
    """加载配置，按优先级合并多个来源。

    优先级（高到低）：
    1. CLI 参数（token, user_id, host）
    2. cookie 参数
    3. 配置文件
    4. 环境变量
    """
    data: dict[str, Any] = {}

    # 1. 从配置文件加载
    for p in _config_search_paths(config_path):
        if p.is_file():
            try:
                data = json.loads(p.read_text())
                data["_loaded_from"] = str(p)
            except json.JSONDecodeError:
                continue
            break

    # 2. 环境变量覆盖（包括 ZEPP_COOKIE）
    for field_name, env_name in ENV_MAP.items():
        v = os.environ.get(env_name, "").strip()
        if v:
            data[field_name] = v

    # 3. cookie 参数覆盖
    if cookie:
        cookie_data = parse_cookie(cookie)
        data.update(cookie_data)

    # 4. CLI 参数最高优先级
    if token:
        data["app_token"] = token
    if user_id:
        data["user_id"] = user_id
    if host:
        data["host"] = host

    # 如果有 cookie 字段但没有显式解析过，解析它
    if "cookie" in data and not data.get("app_token"):
        cookie_data = parse_cookie(data.pop("cookie"))
        # cookie 解析的值优先级低于显式配置
        for k, v in cookie_data.items():
            if k not in data or not data[k]:
                data[k] = v
    else:
        data.pop("cookie", None)

    # 清理非配置字段
    data.pop("_loaded_from", None)

    # 设置默认 host
    if not data.get("host"):
        region = data.get("region", "1")
        data["host"] = REGION_HOSTS.get(region, DEFAULT_HOST)

    return AppConfig(**{k: v for k, v in data.items() if k in AppConfig.model_fields})


def save_config(data: dict[str, Any], path: Path) -> Path:
    """保存配置到文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: v for k, v in data.items() if k in AppConfig.model_fields and v}
    path.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path
