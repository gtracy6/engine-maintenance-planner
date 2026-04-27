"""Cached YAML loader for engine-type and fleet-scenario configs."""

from functools import cache
from pathlib import Path

import yaml

from app.core.engine_config import EngineTypeConfig, ScenarioConfig

_CONFIG_ROOT = Path(__file__).parent.parent.parent / "config"
_ENGINE_TYPES_DIR = _CONFIG_ROOT / "engine_types"
_SCENARIOS_DIR = _CONFIG_ROOT / "scenarios"


@cache
def get_engine_type(name: str) -> EngineTypeConfig:
    path = _ENGINE_TYPES_DIR / f"{name.lower()}.yaml"
    if not path.exists():
        raise ValueError(f"Engine type '{name}' not found. Available: {list_engine_types()}")
    return EngineTypeConfig(**yaml.safe_load(path.read_text()))


@cache
def get_scenario(name: str) -> ScenarioConfig:
    path = _SCENARIOS_DIR / f"{name.lower()}.yaml"
    if not path.exists():
        raise ValueError(f"Scenario '{name}' not found. Available: {list_scenarios()}")
    return ScenarioConfig(**yaml.safe_load(path.read_text()))


def list_engine_types() -> list[str]:
    return sorted(p.stem for p in _ENGINE_TYPES_DIR.glob("*.yaml"))


def list_scenarios() -> list[str]:
    return sorted(p.stem for p in _SCENARIOS_DIR.glob("*.yaml"))
