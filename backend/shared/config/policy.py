"""Typed access to policy.yaml (business thresholds)."""

from functools import lru_cache

import yaml
from pydantic import BaseModel

from shared.config.settings import get_settings


class Planning(BaseModel):
    service_level_z: float = 1.65
    default_review_period_days: int = 7
    accept_tolerance_pct: float = 5
    shelf_life_sell_buffer_days: int = 1


class Costs(BaseModel):
    holding_cost_pct_per_day: float = 0.1
    stockout_cost_multiplier: float = 2.0


class DataQuality(BaseModel):
    stale_count_days: int = 7
    forecast_vs_sales_ratio_max: float = 1.5


class HardRules(BaseModel):
    max_expiry_waste_pct: float = 5


class SoftRules(BaseModel):
    po_value_over: float = 2000
    increase_over_recommendation_pct: float = 30
    express_premium_total_over: float = 100
    min_supplier_fill_rate: float = 0.85


class LoopLimits(BaseModel):
    max_tool_calls: int = 25
    max_revisions: int = 2
    max_replans: int = 2
    max_llm_format_retries: int = 2


class Verification(BaseModel):
    unacceptable_if_lost_units_over: float = 0
    degraded_ok_if_min_stock_over_ss_pct: float = 50


class Policy(BaseModel):
    planning: Planning = Planning()
    costs: Costs = Costs()
    data_quality: DataQuality = DataQuality()
    hard_rules: HardRules = HardRules()
    soft_rules: SoftRules = SoftRules()
    loop_limits: LoopLimits = LoopLimits()
    verification: Verification = Verification()


def load_policy(path=None) -> Policy:
    settings = get_settings()
    file = settings.resolve(path or settings.policy_path)
    return Policy.model_validate(yaml.safe_load(file.read_text()) or {})


@lru_cache
def get_policy() -> Policy:
    return load_policy()
