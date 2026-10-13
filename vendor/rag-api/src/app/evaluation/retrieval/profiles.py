"""Retrieval evaluation profile 與 benchmark strategy lane 的資料驅動 registry。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.settings import AppSettings


# 正式 production-like benchmark profile 名稱。
PRODUCTION_LIKE_V1 = "production_like_v1"
# 離線 deterministic regression gate profile 名稱。
DETERMINISTIC_GATE_V1 = "deterministic_gate_v1"
# 通用 assembler lane 第一輪 profile 名稱。
GENERIC_GUARDED_ASSEMBLER_V1 = "generic_guarded_assembler_v1"
# 通用 assembler lane 第二輪 profile 名稱。
GENERIC_GUARDED_ASSEMBLER_V2 = "generic_guarded_assembler_v2"
# 通用 assembler lane 第一輪 deterministic gate profile 名稱。
GENERIC_GUARDED_ASSEMBLER_V1_GATE = "generic_guarded_assembler_v1_gate"
# 通用 assembler lane 第二輪 deterministic gate profile 名稱。
GENERIC_GUARDED_ASSEMBLER_V2_GATE = "generic_guarded_assembler_v2_gate"
# 無需進入 iteration 的 effect-check 假設名稱。
HYPOTHESIS_NONE = "no_iteration_needed"
# rerank hit 但 assembled drop 的假設名稱。
HYPOTHESIS_ASSEMBLER = "assembler_retention_guard"
# guarded profile 的安全上限，避免 benchmark-only 調參失控。
MAX_GUARDED_RECALL_DEPTH = 100


@dataclass(frozen=True, slots=True)
class EvaluationProfileSpec:
    """單一 evaluation profile 的資料驅動定義。"""

    name: str  # profile 名稱。
    overrides: dict[str, int | str | bool] = field(default_factory=dict)  # 直接覆寫欄位。
    base_profile: str | None = None  # 若需繼承其他 profile，填入 base profile 名稱。
    is_gate: bool = False  # 是否為 deterministic gate profile。
    lane_name: str | None = None  # 所屬策略 lane 名稱；非 guarded profile 可為空。


@dataclass(frozen=True, slots=True)
class BenchmarkStrategyLaneSpec:
    """單一 benchmark 策略 lane 定義。"""

    name: str  # lane 名稱。
    main_hypothesis: str  # effect-check / rollback 使用的唯一主假設。
    profile_sequence: tuple[str, ...]  # 此 lane 依序允許的 live guarded profiles。
    rollback_target_hypothesis: str | None = None  # rollback 後允許切換的下一個主假設。


def _deterministic_gate_overrides(*, settings: AppSettings) -> dict[str, int | str | bool]:
    """建立 deterministic gate v1 的覆寫欄位。

    參數：
    - `settings`：目前應用程式設定。

    回傳：
    - `dict[str, int | str | bool]`：deterministic gate v1 的設定覆寫。
    """

    return {
        "rerank_provider": "deterministic",
        "rerank_top_n": min(settings.rerank_top_n, 4),
        "retrieval_vector_top_k": min(settings.retrieval_vector_top_k, 6),
        "retrieval_fts_top_k": min(settings.retrieval_fts_top_k, 6),
        "retrieval_max_candidates": min(settings.retrieval_max_candidates, 8),
        "assembler_max_contexts": min(settings.assembler_max_contexts, 4),
        "assembler_max_children_per_parent": min(settings.assembler_max_children_per_parent, 2),
    }


def _generic_guarded_assembler_v1_overrides(*, settings: AppSettings) -> dict[str, int | str | bool]:
    """建立 `generic_guarded_assembler_v1` 的覆寫欄位。

    參數：
    - `settings`：目前應用程式設定。

    回傳：
    - `dict[str, int | str | bool]`：assembler v1 的設定覆寫。
    """

    return {
        "rerank_top_n": min(max(settings.rerank_top_n, 8), MAX_GUARDED_RECALL_DEPTH),
        "assembler_max_contexts": max(settings.assembler_max_contexts, 8),
        "assembler_max_chars_per_context": max(settings.assembler_max_chars_per_context, 3200),
        "assembler_max_children_per_parent": max(settings.assembler_max_children_per_parent, 4),
    }


def _generic_guarded_assembler_v2_overrides(*, settings: AppSettings) -> dict[str, int | str | bool]:
    """建立 `generic_guarded_assembler_v2` 的覆寫欄位。

    參數：
    - `settings`：目前應用程式設定。

    回傳：
    - `dict[str, int | str | bool]`：assembler v2 的設定覆寫。
    """

    return {
        "rerank_top_n": min(max(settings.rerank_top_n, 10), MAX_GUARDED_RECALL_DEPTH),
        "assembler_max_contexts": max(settings.assembler_max_contexts, 10),
        "assembler_max_chars_per_context": max(settings.assembler_max_chars_per_context, 3600),
        "assembler_max_children_per_parent": max(settings.assembler_max_children_per_parent, 5),
    }


EVALUATION_PROFILE_SPECS: dict[str, EvaluationProfileSpec] = {
    PRODUCTION_LIKE_V1: EvaluationProfileSpec(
        name=PRODUCTION_LIKE_V1,
        overrides={},
    ),
    DETERMINISTIC_GATE_V1: EvaluationProfileSpec(
        name=DETERMINISTIC_GATE_V1,
        overrides={},
    ),
    GENERIC_GUARDED_ASSEMBLER_V1: EvaluationProfileSpec(
        name=GENERIC_GUARDED_ASSEMBLER_V1,
        lane_name="assembler",
    ),
    GENERIC_GUARDED_ASSEMBLER_V2: EvaluationProfileSpec(
        name=GENERIC_GUARDED_ASSEMBLER_V2,
        lane_name="assembler",
    ),
    GENERIC_GUARDED_ASSEMBLER_V1_GATE: EvaluationProfileSpec(
        name=GENERIC_GUARDED_ASSEMBLER_V1_GATE,
        base_profile=GENERIC_GUARDED_ASSEMBLER_V1,
        overrides={"rerank_provider": "deterministic"},
        is_gate=True,
        lane_name="assembler",
    ),
    GENERIC_GUARDED_ASSEMBLER_V2_GATE: EvaluationProfileSpec(
        name=GENERIC_GUARDED_ASSEMBLER_V2_GATE,
        base_profile=GENERIC_GUARDED_ASSEMBLER_V2,
        overrides={"rerank_provider": "deterministic"},
        is_gate=True,
        lane_name="assembler",
    ),
}


BENCHMARK_STRATEGY_LANES: dict[str, BenchmarkStrategyLaneSpec] = {
    HYPOTHESIS_ASSEMBLER: BenchmarkStrategyLaneSpec(
        name="assembler",
        main_hypothesis=HYPOTHESIS_ASSEMBLER,
        profile_sequence=(GENERIC_GUARDED_ASSEMBLER_V1, GENERIC_GUARDED_ASSEMBLER_V2),
        rollback_target_hypothesis=None,
    ),
}


# 所有允許的 evaluation profile 名稱。
SUPPORTED_EVALUATION_PROFILES = tuple(EVALUATION_PROFILE_SPECS.keys())

# assembler lane 的固定 profile 順序。
GENERIC_GUARDED_ASSEMBLER_SEQUENCE = BENCHMARK_STRATEGY_LANES[HYPOTHESIS_ASSEMBLER].profile_sequence


def resolve_evaluation_settings(*, settings: AppSettings, evaluation_profile: str) -> AppSettings:
    """依 evaluation profile 產生本次 run 的固定設定。

    參數：
    - `settings`：目前應用程式設定。
    - `evaluation_profile`：要解析的 evaluation profile 名稱。

    回傳：
    - `AppSettings`：套用 profile 後的有效設定。
    """

    overrides = get_evaluation_profile_overrides(settings=settings, evaluation_profile=evaluation_profile)
    return settings.model_copy(update=overrides) if overrides else settings


def get_evaluation_profile_overrides(*, settings: AppSettings, evaluation_profile: str) -> dict[str, int | str | bool]:
    """回傳指定 profile 相對於原始設定的覆寫欄位。

    前置條件與風險：
    - 此函式僅供 benchmark/profile-gated 路徑使用，不得直接用來改 production defaults。
    - strategy/profile 的擴充應優先透過 registry，而非分散 if/else。

    參數：
    - `settings`：目前應用程式設定。
    - `evaluation_profile`：要解析的 evaluation profile 名稱。

    回傳：
    - `dict[str, int | str | bool]`：僅包含發生變化的覆寫欄位。
    """

    if evaluation_profile not in EVALUATION_PROFILE_SPECS:
        raise ValueError(f"不支援的 evaluation profile：{evaluation_profile}")

    if evaluation_profile == DETERMINISTIC_GATE_V1:
        return _deterministic_gate_overrides(settings=settings)
    if evaluation_profile == GENERIC_GUARDED_ASSEMBLER_V1:
        return _generic_guarded_assembler_v1_overrides(settings=settings)
    if evaluation_profile == GENERIC_GUARDED_ASSEMBLER_V2:
        return _generic_guarded_assembler_v2_overrides(settings=settings)

    spec = EVALUATION_PROFILE_SPECS[evaluation_profile]
    merged_overrides: dict[str, int | str | bool] = {}
    if spec.base_profile is not None:
        merged_overrides.update(
            get_evaluation_profile_overrides(settings=settings, evaluation_profile=spec.base_profile)
        )
    merged_overrides.update(spec.overrides)
    return merged_overrides


def get_candidate_profiles_for_hypothesis(*, main_hypothesis: str) -> list[str]:
    """依主假設回傳對應 lane 的 profile 順序。

    參數：
    - `main_hypothesis`：本輪唯一主假設。

    回傳：
    - `list[str]`：對應 lane 的 profile 順序；若無對應 lane 則回空列表。
    """

    lane = BENCHMARK_STRATEGY_LANES.get(main_hypothesis)
    return list(lane.profile_sequence) if lane is not None else []


def get_gate_profile_for_profile(*, profile_name: str) -> str:
    """將 live guarded profile 映射為 deterministic gate profile。

    參數：
    - `profile_name`：live guarded profile 名稱。

    回傳：
    - `str`：對應的 deterministic gate profile 名稱。
    """

    for spec in EVALUATION_PROFILE_SPECS.values():
        if spec.is_gate and spec.base_profile == profile_name:
            return spec.name
    raise KeyError(f"找不到對應的 deterministic gate profile：{profile_name}")


def get_rollback_target_hypothesis(*, main_hypothesis: str) -> str | None:
    """讀取指定主假設在 rollback 後應切換到哪個下一個假設。

    參數：
    - `main_hypothesis`：目前主假設。

    回傳：
    - `str | None`：下一個主假設；若無替代 lane 則回傳 `None`。
    """

    lane = BENCHMARK_STRATEGY_LANES.get(main_hypothesis)
    return lane.rollback_target_hypothesis if lane is not None else None
