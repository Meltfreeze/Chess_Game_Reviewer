import os
import platform
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_DEPTH = int(os.environ.get("ANALYSIS_DEPTH", "18"))
MAX_DEPTH = 22


def get_engine_path():
    env_path = os.environ.get("STOCKFISH_PATH")
    if env_path and os.path.exists(env_path):
        return os.path.abspath(env_path)

    candidates = []
    if platform.system() == "Windows":
        candidates += ["stockfishw.exe", "stockfish.exe", "stockfish-windows-x86-64.exe"]
    else:
        candidates += ["stockfish", "stockfish-ubuntu-x86-64", "stockfish-linux"]

    for name in candidates:
        p = os.path.join(BASE_DIR, name)
        if os.path.exists(p):
            if platform.system() != "Windows":
                try:
                    os.chmod(p, 0o755)
                except OSError:
                    pass
            return p

    found = shutil.which("stockfish")
    return found


def get_gemini_api_key():
    return os.environ.get("GEMINI_API_KEY")
