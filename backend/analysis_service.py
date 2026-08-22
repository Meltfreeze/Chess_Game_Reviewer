"""Persistent Stockfish engine singleton with analysis caching."""

import hashlib
import json
import threading

import chess.engine

from backend.config import (
    get_engine_path,
    DEFAULT_DEPTH,
    MAX_DEPTH,
    ENGINE_LOCK_TIMEOUT_SECONDS,
)


class AnalysisService:
    _instance = None
    _init_lock = threading.Lock()

    def __init__(self, engine_path):
        self.engine_path = engine_path
        self._engine = None
        self._lock = threading.Lock()
        self._cache = {}

    @classmethod
    def get(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    path = get_engine_path()
                    if path is None:
                        raise RuntimeError("Stockfish binary not found")
                    cls._instance = cls(path)
        return cls._instance

    def _ensure_engine(self):
        if self._engine is None:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            try:
                self._engine.configure({"Threads": 1, "Hash": 32})
            except chess.engine.EngineError:
                pass
        return self._engine

    @property
    def ready(self):
        return self.engine_path is not None

    def health(self):
        info = {"engine_path": self.engine_path, "ready": False, "version": None}
        try:
            engine = self._ensure_engine()
            info["ready"] = True
            info["version"] = engine.id.get("name", "Stockfish")
        except Exception as exc:
            info["error"] = str(exc)
        return info

    def _cache_key(self, pgn, depth, player_color):
        h = hashlib.sha1()
        h.update(pgn.strip().encode())
        h.update(str(depth).encode())
        h.update(player_color.encode())
        return h.hexdigest()

    def get_cached(self, pgn, depth, player_color):
        key = self._cache_key(pgn, depth, player_color)
        return self._cache.get(key)

    def set_cached(self, pgn, depth, player_color, result):
        key = self._cache_key(pgn, depth, player_color)
        self._cache[key] = result

    def analyze_streaming(self, pgn, depth=None, player_color="White"):
        from backend.engine import analyze_game_streaming

        depth = min(MAX_DEPTH, depth or DEFAULT_DEPTH)
        cached = self.get_cached(pgn, depth, player_color)
        if cached:
            yield "cached", cached
            return

        engine = self._ensure_engine()
        complete_payload = None

        if not self._lock.acquire(timeout=ENGINE_LOCK_TIMEOUT_SECONDS):
            raise TimeoutError(
                "Engine is busy analyzing another request. Please try again shortly."
            )
        try:
            for event_type, payload in analyze_game_streaming(pgn, engine, depth):
                if event_type == "complete":
                    complete_payload = payload
                yield event_type, payload
        finally:
            self._lock.release()

        if complete_payload:
            self.set_cached(pgn, depth, player_color, complete_payload)

    def analyse_position(self, fen, depth=None, multipv=3):
        from backend.engine import analyse_fen

        depth = min(MAX_DEPTH, depth or DEFAULT_DEPTH)
        engine = self._ensure_engine()
        if not self._lock.acquire(timeout=ENGINE_LOCK_TIMEOUT_SECONDS):
            raise TimeoutError(
                "Engine is busy analyzing another request. Please try again shortly."
            )
        try:
            return analyse_fen(fen, engine, depth=depth, multipv=multipv)
        finally:
            self._lock.release()

    def shutdown(self):
        if self._engine:
            self._engine.quit()
            self._engine = None
