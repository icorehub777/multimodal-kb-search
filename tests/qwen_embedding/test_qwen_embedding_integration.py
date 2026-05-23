"""
pytest 串接測試：qwen3-vl-embedding 文字、圖片、融合向量。

未設定 DASHSCOPE_API_KEY 或 DASHSCOPE_SKIP=1 時自動略過。
"""

from __future__ import annotations

import pytest

from embedding_helpers import (
    SAMPLE_IMAGE_URL,
    cosine_similarity,
    embed_contents,
    embed_image_url,
    embed_text,
    get_config,
    is_configured,
)

pytestmark = pytest.mark.skipif(
    not is_configured(),
    reason="未設定 DASHSCOPE_API_KEY，或已設 DASHSCOPE_SKIP=1",
)


@pytest.fixture(scope="module")
def embedding_cfg():
    return get_config()


def test_text_embedding_dimension(embedding_cfg):
    vec = embed_text("KBSearch pytest 文字向量測試")
    assert len(vec) == embedding_cfg["dimension"]


def test_image_embedding_dimension(embedding_cfg):
    vec = embed_image_url(SAMPLE_IMAGE_URL)
    assert len(vec) == embedding_cfg["dimension"]


def test_similar_texts_more_similar_than_unrelated():
    query = "合約審閱與法務意見書"
    related = "法律文件審查與合約條款"
    unrelated = "今日午餐推薦與咖啡廳評價"

    v_query = embed_text(query)
    v_related = embed_text(related)
    v_unrelated = embed_text(unrelated)

    sim_related = cosine_similarity(v_query, v_related)
    sim_unrelated = cosine_similarity(v_query, v_unrelated)
    assert sim_related > sim_unrelated


def test_fused_embedding_single_vector(embedding_cfg):
    vectors = embed_contents(
        [{"text": "融合測試"}, {"image": SAMPLE_IMAGE_URL}],
        enable_fusion=True,
    )
    assert len(vectors) == 1
    assert len(vectors[0]) == embedding_cfg["dimension"]
