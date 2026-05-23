"""
qwen3-vl-embedding 端到端串接測試：文字、圖片、融合向量。

執行前請複製 .env.example 為 .env，並填入 DASHSCOPE_API_KEY。

用法：
    python test_qwen_embedding.py
"""

from __future__ import annotations

import sys

from embedding_helpers import (
    SAMPLE_IMAGE_URL,
    cosine_similarity,
    embed_contents,
    embed_image_url,
    embed_text,
    get_config,
    is_configured,
)


def main() -> int:
    if not is_configured():
        print(
            "略過：請設定 .env 中的 DASHSCOPE_API_KEY，"
            "且勿將 DASHSCOPE_SKIP 設為 1。",
            file=sys.stderr,
        )
        return 2

    cfg = get_config()
    dim = cfg["dimension"]
    model = cfg["model"]
    print(f"模型：{model}，維度：{dim}，端點：{cfg['base_url']}")

    try:
        text_a = "知識庫文件分頁向量化的串接測試"
        text_b = "完全不同的無關主題：天氣預報與交通路況"
        vec_a = embed_text(text_a)
        vec_b = embed_text(text_b)
        print(f"文字向量：維度 {len(vec_a)}")

        if len(vec_a) != dim:
            print(f"文字向量維度應為 {dim}，實際 {len(vec_a)}", file=sys.stderr)
            return 1

        sim_same = cosine_similarity(vec_a, vec_a)
        sim_diff = cosine_similarity(vec_a, vec_b)
        print(f"相同文字餘弦相似度：{sim_same:.4f}（應接近 1）")
        print(f"不同文字餘弦相似度：{sim_diff:.4f}")

        if sim_same < 0.99:
            print("相同文字相似度異常偏低。", file=sys.stderr)
            return 1

        vec_img = embed_image_url(SAMPLE_IMAGE_URL)
        print(f"圖片向量：維度 {len(vec_img)}")
        if len(vec_img) != dim:
            print(f"圖片向量維度應為 {dim}，實際 {len(vec_img)}", file=sys.stderr)
            return 1

        fused = embed_contents(
            [
                {"text": "產品說明：白色運動鞋"},
                {"image": SAMPLE_IMAGE_URL},
            ],
            enable_fusion=True,
        )
        print(f"融合向量：{len(fused)} 筆，維度 {len(fused[0])}")
        if len(fused) != 1 or len(fused[0]) != dim:
            print("融合模式應回傳單一 2560 維向量。", file=sys.stderr)
            return 1

        print("全部通過：文字、圖片、融合 Embedding 皆正常。")
        return 0
    except Exception as exc:
        print(f"發生錯誤：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
