import { describe, expect, it } from "vitest";
import { findOpening, parseOpeningTable } from "./openingLookup";
import { formatPgnDate, parsePgnPreview } from "./pgnPreview";

const SCHOLARS_MATE = `[Event "Casual Game"]
[Site "Anywhere"]
[Date "2026.08.29"]
[Round "1"]
[White "Scholar"]
[Black "Opponent"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0`;

describe("PGN preview parsing", () => {
  it("derives the completed-game preview and check state", () => {
    const parsed = parsePgnPreview(SCHOLARS_MATE);

    expect(parsed.kind).toBe("valid");
    if (parsed.kind !== "valid") return;
    expect(parsed.preview).toMatchObject({
      white: "Scholar",
      black: "Opponent",
      resultLabel: "1–0",
      date: "29 Aug 2026",
      moveCount: 4,
      event: "Casual Game",
      termination: "checkmate",
      lastMove: { from: "h5", to: "f7" },
      checkedKingSquare: "e8",
    });
  });

  it("finds the longest matching opening prefix", () => {
    const parsed = parsePgnPreview(SCHOLARS_MATE);
    expect(parsed.kind).toBe("valid");
    if (parsed.kind !== "valid") return;
    const table = parseOpeningTable(
      "uci\teco\tname\n" +
      "e2e4 e7e5\tC20\tKing's Pawn Game\n" +
      "e2e4 e7e5 f1c4 b8c6\tC23\tBishop's Opening\n"
    );

    expect(findOpening(table, parsed.preview.uciMoves)).toEqual({
      eco: "C23",
      name: "Bishop's Opening",
    });
  });

  it("reports the first illegal move without leaking parser errors", () => {
    const parsed = parsePgnPreview(SCHOLARS_MATE.replace("Nf6", "Nf5"));

    expect(parsed).toEqual({
      kind: "invalid",
      reason: "Move 3 (Nf5) isn't legal in this position. Check the notation and try again.",
    });
  });

  it("distinguishes headers without moves from non-PGN text", () => {
    expect(parsePgnPreview('[Event "Empty"]')).toEqual({
      kind: "invalid",
      reason: "No moves found. Add the moves after the headers.",
    });
    expect(parsePgnPreview("this is ordinary prose")).toEqual({
      kind: "invalid",
      reason: "This doesn't look like a PGN. Paste the moves in standard notation or upload a .pgn file.",
    });
  });

  it("rejects non-standard variants", () => {
    const parsed = parsePgnPreview('[Variant "Chess960"]\n\n1. e4 e5');
    expect(parsed).toEqual({
      kind: "invalid",
      reason: "Only standard chess is supported right now.",
    });
  });

  it("rejects a PGN containing multiple games", () => {
    const parsed = parsePgnPreview(`[Event "First game"]
[White "First"]
[Black "Player"]

1. e4 e5 1-0

[Event "Second game"]
[White "Later"]
[Black "Ignored"]

1. d4 d5 0-1`);

    expect(parsed).toEqual({
      kind: "invalid",
      reason: "This PGN contains 2 games. Paste one game at a time.",
    });
  });

  it("uses header fallbacks and accepts trailing whitespace", () => {
    const parsed = parsePgnPreview(`[Date "2026.??.??"]
[White "?"]
[Black ""]

1. e4 e5 *

   `);

    expect(parsed.kind).toBe("valid");
    if (parsed.kind !== "valid") return;
    expect(parsed.preview).toMatchObject({
      white: "White",
      black: "Black",
      date: "2026",
      resultLabel: "No result",
      moveCount: 1,
    });
    expect(parsed.preview.sourcePgn.endsWith("*")).toBe(true);
  });

  it("formats complete and partial PGN dates", () => {
    expect(formatPgnDate("2026.08.29")).toBe("29 Aug 2026");
    expect(formatPgnDate("2026.08.??")).toBe("Aug 2026");
    expect(formatPgnDate("2026.??.??")).toBe("2026");
    expect(formatPgnDate("????.??.??")).toBeUndefined();
  });

  it("keeps a declared agreed draw and its termination", () => {
    const parsed = parsePgnPreview(`[Result "1/2-1/2"]
[Termination "Draw by agreement"]

1. Nf3 Nf6 2. Ng1 Ng8 1/2-1/2`);

    expect(parsed.kind).toBe("valid");
    if (parsed.kind !== "valid") return;
    expect(parsed.preview.resultLabel).toBe("½–½");
    expect(parsed.preview.termination).toBe("agreed draw");
  });

  it("treats an unknown result marker as no result", () => {
    const parsed = parsePgnPreview('[Result "?"]\n\n1. e4 e5 ?');
    expect(parsed.kind).toBe("valid");
    if (parsed.kind !== "valid") return;
    expect(parsed.preview.resultLabel).toBe("No result");
  });
});
