import pytest


@pytest.fixture(autouse=True)
def enable_testing_mock_mode(monkeypatch):
    """全局自动开启 DITING_MOCK_MODE 隔离外部 LLM 真实网络请求。"""
    monkeypatch.setenv("DITING_MOCK_MODE", "true")
