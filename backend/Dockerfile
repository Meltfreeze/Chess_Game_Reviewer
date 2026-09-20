FROM python:3.11-slim
WORKDIR /app

ARG STOCKFISH_URL=https://media.githubusercontent.com/media/Meltfreeze/Chess_Game_Reviewer/main/stockfish
ARG STOCKFISH_SHA256=0f83d24cc46d2c66c60f16001af5444873bc112b7d028594513426894c12da19

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl --fail --location --retry 3 --output /usr/local/bin/stockfish "$STOCKFISH_URL" \
    && echo "$STOCKFISH_SHA256  /usr/local/bin/stockfish" | sha256sum -c - \
    && chmod 0755 /usr/local/bin/stockfish \
    && printf 'uci\nquit\n' | /usr/local/bin/stockfish | grep -q '^id name Stockfish 19$' \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY icons/ ./icons/

ENV PORT=8000
ENV STOCKFISH_PATH=/usr/local/bin/stockfish
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
