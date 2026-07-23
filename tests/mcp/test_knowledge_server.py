from mcp.knowledge_server import search_runbooks_engine


def test_bm25_search_recall_under_noise():
    # 输入相关故障关键词，验证能够在 10+ 篇干扰文档下精确定位 Top-1 为 redis_pool_leak.md
    results = search_runbooks_engine("Redis connection pool leak", top_k=3)
    assert len(results) > 0
    assert results[0]["filename"] == "redis_pool_leak.md"
    assert results[0]["score"] > 0

    # 输入 OOM 关键词，验证能够精确定位 service_oom.md
    oom_results = search_runbooks_engine("OutOfMemoryError Java heap space", top_k=3)
    assert len(oom_results) > 0
    assert oom_results[0]["filename"] == "service_oom.md"
