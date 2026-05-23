"""
阿里雲 DashScope qwen3-vl-embedding 串接輔助。

對應設計規格中的「每頁圖片向量化」與「查詢向量」；供 indexer 與測試重用。
"""

from __future__ import annotations

import math
import os
from http import HTTPStatus
from pathlib import Path
from typing import Any

import dashscope
from dashscope import MultiModalEmbedding
from dotenv import load_dotenv

DEFAULT_MODEL = "qwen3-vl-embedding"
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
DEFAULT_DIMENSION = 2560

# 官方範例公開測試圖（僅供串接驗證）
SAMPLE_IMAGE_URL = (
    "https://dashscope.oss-cn-beijing.aliyuncs.com/images/256_1.png"
)

_ENV_LOADED = False


def _load_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    load_dotenv(Path(__file__).resolve().parent / ".env")
    _ENV_LOADED = True


def get_config() -> dict[str, Any]:
    """讀取環境變數設定。"""
    _load_env()
    return {
        "api_key": os.environ.get("DASHSCOPE_API_KEY", "").strip(),
        "model": os.environ.get("DASHSCOPE_EMBEDDING_MODEL", DEFAULT_MODEL).strip(),
        "base_url": os.environ.get("DASHSCOPE_BASE_URL", DEFAULT_BASE_URL).strip(),
        "dimension": int(os.environ.get("EMBEDDING_DIMENSION", str(DEFAULT_DIMENSION))),
        "skip": os.environ.get("DASHSCOPE_SKIP", "").strip() in ("1", "true", "yes"),
    }


def is_configured() -> bool:
    cfg = get_config()
    if cfg["skip"]:
        return False
    return bool(cfg["api_key"])


def configure_client() -> dict[str, Any]:
    """套用 API Key 與端點，回傳目前設定。"""
    cfg = get_config()
    if not cfg["api_key"]:
        raise RuntimeError(
            "未設定 DASHSCOPE_API_KEY（請於 .env 填入百煉 API Key）"
        )
    dashscope.api_key = cfg["api_key"]
    dashscope.base_http_api_url = cfg["base_url"]
    return cfg


def embed_contents(
    contents: list[dict[str, str]],
    *,
    enable_fusion: bool = False,
    dimension: int | None = None,
) -> list[list[float]]:
    """
    呼叫多模態 Embedding API。

    contents: 例如 [{"text": "..."}] 或 [{"image": "https://..."}]
    enable_fusion: True 時將多筆輸入融合為單一向量（僅 qwen3-vl-embedding）
    回傳 embedding 向量列表（與 API output.embeddings 順序一致）。
    """
    cfg = configure_client()
    dim = dimension if dimension is not None else cfg["dimension"]

    kwargs: dict[str, Any] = {
        "model": cfg["model"],
        "input": contents,
        "api_key": cfg["api_key"],
    }
    if enable_fusion:
        kwargs["enable_fusion"] = True
    if dim != DEFAULT_DIMENSION:
        kwargs["parameters"] = {"dimension": dim}

    resp = MultiModalEmbedding.call(**kwargs)
    if resp.status_code != HTTPStatus.OK:
        code = getattr(resp, "code", "") or ""
        message = getattr(resp, "message", "") or str(resp)
        raise RuntimeError(
            f"Embedding API 失敗 (HTTP {resp.status_code}): {code} {message}".strip()
        )

    output = resp.output or {}
    embeddings = output.get("embeddings") or []
    vectors: list[list[float]] = []
    for item in embeddings:
        vec = item.get("embedding")
        if not vec:
            raise RuntimeError("API 回應缺少 embedding 向量")
        vectors.append(list(vec))
    if not vectors:
        raise RuntimeError("API 未回傳任何 embedding")
    return vectors


def embed_text(text: str, *, enable_fusion: bool = False) -> list[float]:
    """單段文字 → 向量。"""
    vectors = embed_contents([{"text": text}], enable_fusion=enable_fusion)
    return vectors[0]


def embed_image_url(url: str, *, enable_fusion: bool = False) -> list[float]:
    """公開圖片 URL → 向量。"""
    vectors = embed_contents([{"image": url}], enable_fusion=enable_fusion)
    return vectors[0]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """餘弦相似度（用於串接測試驗證）。"""
    if len(a) != len(b):
        raise ValueError(f"向量維度不一致: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
