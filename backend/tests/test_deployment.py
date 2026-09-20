"""Regression checks for the production Stockfish image configuration."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_installs_and_selects_pinned_stockfish_19():
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert "media.githubusercontent.com/media/Meltfreeze/Chess_Game_Reviewer/main/stockfish" in dockerfile
    assert "0f83d24cc46d2c66c60f16001af5444873bc112b7d028594513426894c12da19" in dockerfile
    assert "sha256sum -c -" in dockerfile
    assert "^id name Stockfish 19$" in dockerfile
    assert "ENV STOCKFISH_PATH=/usr/local/bin/stockfish" in dockerfile
    assert "ENV STOCKFISH_PATH=/usr/games/stockfish" not in dockerfile
