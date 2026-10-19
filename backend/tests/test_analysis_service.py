"""Engine resource settings and analysis cache isolation."""

from backend import analysis_service


def test_engine_resources_are_configured_from_settings(monkeypatch):
    configured = []

    class FakeEngine:
        def configure(self, options):
            configured.append(options)

    fake = FakeEngine()
    monkeypatch.setattr(
        analysis_service.chess.engine.SimpleEngine,
        "popen_uci",
        lambda _path: fake,
    )
    monkeypatch.setattr(analysis_service, "ENGINE_THREADS", 2)
    monkeypatch.setattr(analysis_service, "ENGINE_HASH_MB", 128)

    service = analysis_service.AnalysisService("stockfish")
    assert service._ensure_engine() is fake
    assert service._ensure_engine() is fake
    assert configured == [{"Threads": 2, "Hash": 128}]


def test_cache_key_changes_with_analysis_settings(monkeypatch):
    service = analysis_service.AnalysisService("stockfish")
    original = service._cache_key("1. e4", 16)
    monkeypatch.setattr(analysis_service, "FAST_ANALYSIS_DEPTH", 12)
    assert service._cache_key("1. e4", 16) != original
    monkeypatch.setattr(analysis_service, "FAST_ANALYSIS_DEPTH", 10)
    monkeypatch.setattr(analysis_service, "ENGINE_THREADS", 2)
    assert service._cache_key("1. e4", 16) != original
