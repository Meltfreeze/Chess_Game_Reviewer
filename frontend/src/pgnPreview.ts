import { Chess } from "chess.js";

export type PreviewResult = "1-0" | "0-1" | "1/2-1/2" | null;

export interface GamePreview {
  sourcePgn: string;
  white: string;
  black: string;
  whiteElo?: string;
  blackElo?: string;
  result: PreviewResult;
  resultLabel: "1–0" | "0–1" | "½–½" | "No result";
  opening?: string;
  eco?: string;
  date?: string;
  event?: string;
  moveCount: number;
  termination?: string;
  fen: string;
  lastMove?: { from: string; to: string };
  checkedKingSquare?: string;
  uciMoves: string[];
}

export type PgnParseState =
  | { kind: "empty" }
  | { kind: "invalid"; reason: string }
  | { kind: "valid"; preview: GamePreview };

const RESULT_TOKENS = new Set(["1-0", "0-1", "1/2-1/2", "½-½", "*", "?"]);
const MOVE_TOKEN = /^(?:[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O(?:-O)?[+#]?)$/;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function parsePgnPreview(rawPgn: string): PgnParseState {
  const trimmed = rawPgn.trim();
  if (!trimmed) return { kind: "empty" };

  const games = splitPgnGames(trimmed);
  if (games.length > 1) {
    return {
      kind: "invalid",
      reason: `This PGN contains ${games.length} games. Paste one game at a time.`,
    };
  }
  const sourcePgn = trimmed;
  const headers = extractHeaders(sourcePgn);
  const variant = cleanHeader(headers.Variant);
  if (variant && variant.toLowerCase() !== "standard") {
    return { kind: "invalid", reason: "Only standard chess is supported right now." };
  }

  const moveTokens = extractMoveTokens(sourcePgn);
  const looksLikePgn = Object.keys(headers).length > 0 || moveTokens.some((token) => MOVE_TOKEN.test(token.san));
  if (!looksLikePgn) {
    return {
      kind: "invalid",
      reason: "This doesn't look like a PGN. Paste the moves in standard notation or upload a .pgn file.",
    };
  }

  const chess = new Chess();
  try {
    // Some exporters append `?` as an unknown result marker. It is not part of
    // the PGN grammar, but the product treats it like `*`/a missing result.
    chess.loadPgn(sourcePgn.replace(/(^|\s)\?(?=\s*$)/, "$1"));
  } catch {
    const failure = findFirstIllegalMove(sourcePgn, headers);
    if (failure) {
      return {
        kind: "invalid",
        reason: `Move ${failure.moveNumber} (${failure.san}) isn't legal in this position. Check the notation and try again.`,
      };
    }
    return {
      kind: "invalid",
      reason: "This doesn't look like a PGN. Paste the moves in standard notation or upload a .pgn file.",
    };
  }

  const history = chess.history({ verbose: true });
  if (history.length === 0) {
    return {
      kind: "invalid",
      reason: "No moves found. Add the moves after the headers.",
    };
  }

  const loadedHeaders = { ...headers, ...chess.getHeaders() };
  const result = deriveResult(cleanHeader(loadedHeaders.Result), chess);
  const termination = deriveTermination(cleanHeader(loadedHeaders.Termination), chess);
  const last = history[history.length - 1];
  const checkedKingSquare = chess.isCheck() ? kingSquare(chess.fen(), chess.turn()) : undefined;

  return {
    kind: "valid",
    preview: {
      sourcePgn,
      white: cleanHeader(loadedHeaders.White) ?? "White",
      black: cleanHeader(loadedHeaders.Black) ?? "Black",
      whiteElo: cleanHeader(loadedHeaders.WhiteElo),
      blackElo: cleanHeader(loadedHeaders.BlackElo),
      result,
      resultLabel: resultLabel(result),
      opening: cleanHeader(loadedHeaders.Opening),
      eco: cleanHeader(loadedHeaders.ECO),
      date: formatPgnDate(cleanHeader(loadedHeaders.Date)),
      event: cleanHeader(loadedHeaders.Event),
      moveCount: Math.ceil(history.length / 2),
      termination,
      fen: chess.fen(),
      lastMove: last ? { from: last.from, to: last.to } : undefined,
      checkedKingSquare,
      uciMoves: history.map((move) => move.lan),
    },
  };
}

export function formatPgnDate(value?: string): string | undefined {
  if (!value) return undefined;
  const [year, month, day] = value.split(".");
  if (!/^\d{4}$/.test(year)) return undefined;
  const monthNumber = /^\d{2}$/.test(month) ? Number(month) : 0;
  const dayNumber = /^\d{2}$/.test(day) ? Number(day) : 0;
  if (monthNumber < 1 || monthNumber > 12) return year;
  if (dayNumber < 1 || dayNumber > 31) return `${MONTHS[monthNumber - 1]} ${year}`;
  return `${dayNumber} ${MONTHS[monthNumber - 1]} ${year}`;
}

function cleanHeader(value?: string): string | undefined {
  const clean = value?.trim();
  return clean && clean !== "?" ? clean : undefined;
}

function splitPgnGames(pgn: string): string[] {
  const games: string[] = [];
  let current: string[] = [];
  let hasMovetext = false;

  for (const line of pgn.replace(/^\uFEFF/, "").split(/\r?\n/)) {
    const isHeader = /^\s*\[[A-Za-z0-9_]+\s+"/.test(line);
    if (isHeader && hasMovetext) {
      games.push(current.join("\n").trim());
      current = [];
      hasMovetext = false;
    }
    current.push(line);
    if (line.trim() && !isHeader && !line.trim().startsWith("%")) hasMovetext = true;
  }
  if (current.some((line) => line.trim())) games.push(current.join("\n").trim());
  return games.length ? games : [pgn];
}

function extractHeaders(pgn: string): Record<string, string> {
  const headers: Record<string, string> = {};
  for (const match of pgn.matchAll(/^\s*\[([A-Za-z0-9_]+)\s+"((?:\\.|[^"])*)"\s*\]\s*$/gm)) {
    headers[match[1]] = match[2].replace(/\\"/g, '"').replace(/\\\\/g, "\\");
  }
  return headers;
}

function extractMoveTokens(pgn: string): Array<{ san: string; moveNumber?: number }> {
  let text = pgn
    .replace(/^\s*\[[^\n]*\]\s*$/gm, " ")
    .replace(/\{[^}]*\}/gs, " ")
    .replace(/;[^\n]*/g, " ")
    .replace(/\$\d+/g, " ");

  let previous: string;
  do {
    previous = text;
    text = text.replace(/\([^()]*\)/g, " ");
  } while (text !== previous);

  const moves: Array<{ san: string; moveNumber?: number }> = [];
  let statedMoveNumber: number | undefined;
  for (const raw of text.split(/\s+/).filter(Boolean)) {
    let token = raw;
    const numbered = token.match(/^(\d+)\.(?:\.\.)?(.*)$/);
    if (numbered) {
      statedMoveNumber = Number(numbered[1]);
      token = numbered[2];
    }
    if (!token || token === "..." || RESULT_TOKENS.has(token)) continue;
    token = token.replace(/[!?]+$/g, "");
    moves.push({ san: token, moveNumber: statedMoveNumber });
  }
  return moves;
}

function findFirstIllegalMove(pgn: string, headers: Record<string, string>) {
  let chess: Chess;
  try {
    chess = headers.SetUp === "1" && cleanHeader(headers.FEN)
      ? new Chess(headers.FEN)
      : new Chess();
  } catch {
    return null;
  }

  for (const token of extractMoveTokens(pgn)) {
    const moveNumber = token.moveNumber ?? Number(chess.fen().split(" ")[5]);
    try {
      chess.move(token.san);
    } catch {
      return { san: token.san, moveNumber };
    }
  }
  return null;
}

function deriveResult(headerResult: string | undefined, chess: Chess): PreviewResult {
  if (headerResult === "1-0" || headerResult === "0-1" || headerResult === "1/2-1/2") {
    return headerResult;
  }
  if (chess.isCheckmate()) return chess.turn() === "w" ? "0-1" : "1-0";
  if (chess.isStalemate() || chess.isThreefoldRepetition() || chess.isInsufficientMaterial() || chess.isDrawByFiftyMoves()) {
    return "1/2-1/2";
  }
  return null;
}

function resultLabel(result: PreviewResult): GamePreview["resultLabel"] {
  if (result === "1-0") return "1–0";
  if (result === "0-1") return "0–1";
  if (result === "1/2-1/2") return "½–½";
  return "No result";
}

function deriveTermination(headerTermination: string | undefined, chess: Chess): string | undefined {
  const lower = headerTermination?.toLowerCase();
  if (lower && lower !== "normal" && lower !== "unterminated") {
    if (lower.includes("resign")) return "resignation";
    if (lower.includes("stalemate")) return "stalemate";
    if (lower.includes("repetition")) return "repetition";
    if (lower.includes("insufficient")) return "insufficient material";
    if (lower.includes("50") || lower.includes("fifty")) return "50-move rule";
    if (lower.includes("agreement") || lower.includes("agreed")) return "agreed draw";
    if (lower.includes("checkmate")) return "checkmate";
    return lower;
  }
  if (chess.isCheckmate()) return "checkmate";
  if (chess.isStalemate()) return "stalemate";
  if (chess.isThreefoldRepetition()) return "repetition";
  if (chess.isInsufficientMaterial()) return "insufficient material";
  if (chess.isDrawByFiftyMoves()) return "50-move rule";
  return undefined;
}

function kingSquare(fen: string, turn: "w" | "b"): string | undefined {
  const target = turn === "w" ? "K" : "k";
  const rows = fen.split(" ")[0].split("/");
  for (let row = 0; row < rows.length; row += 1) {
    let file = 0;
    for (const symbol of rows[row]) {
      if (/\d/.test(symbol)) {
        file += Number(symbol);
      } else {
        if (symbol === target) return `${String.fromCharCode(97 + file)}${8 - row}`;
        file += 1;
      }
    }
  }
  return undefined;
}
