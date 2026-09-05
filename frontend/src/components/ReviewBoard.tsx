import { useEffect, useMemo, useRef, useState } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import type { CustomPieces, Piece, Square } from "react-chessboard/dist/chessboard/types";
import type { Classification } from "../types";
import { iconUrl } from "../api/client";
import { BADGE_COLORS } from "../constants";

/** Piece glide, captured-piece fade and last-move highlight all run on this clock. */
const ANIMATION_MS = 180;

const LAST_MOVE_FROM = "rgba(246, 246, 105, 0.72)";
const LAST_MOVE_TO = "rgba(186, 202, 43, 0.72)";

/**
 * A selected piece's own square, tinted the same colour a played move's landing
 * square gets, so selection reads as "live" and — per the spec — wins over a
 * last-move highlight when the two coincide.
 */
const SELECTED_SQUARE_BG = LAST_MOVE_TO;

/**
 * Legal-move hints, painted through customSquareStyles (the board's existing
 * overlay channel) as backgroundImage. That layers them over the last-move /
 * selection backgroundColor without disturbing its fade — the square's only
 * transition is on background-color — so hints snap in the instant a piece is
 * selected.
 *
 *  - dot  : a quiet move, a small grey disc centred on an empty square.
 *  - ring : a capture, a grey annulus reaching the square's four edges that
 *           frames the enemy piece (the piece is the square's child, on top).
 */
const LEGAL_DOT =
  "radial-gradient(circle at center, rgba(0, 0, 0, 0.16) 20%, transparent 21%)";
const LEGAL_RING =
  "radial-gradient(circle closest-side at center, transparent 79%, rgba(0, 0, 0, 0.16) 80%, rgba(0, 0, 0, 0.16) 99%, transparent 100%)";

const PIECE_NAMES: Record<string, string> = {
  P: "Pawn",
  N: "Knight",
  B: "Bishop",
  R: "Rook",
  Q: "Queen",
  K: "King",
};

/** A piece on its way off the board, identified by code as well as square. */
type FadingPiece = { square: string; piece: string };

/**
 * Piece renderers, rebuilt whenever one of them needs to fade out.
 *
 * react-chessboard exposes no per-piece prop for this, so the departing piece has
 * to be closed over here. Callers must memoise the result: the board copies
 * customPieces into state, so a fresh object every render is an update loop.
 */
function buildPieces(fading: FadingPiece | null): CustomPieces {
  // Square as well as code, because `fading` outlives the animation: once the
  // capturer lands on that square it is a different code, so it stays visible
  // without anything having to clear the entry.
  const isFading = (pieceKey: Piece, square?: Square) =>
    fading !== null && fading.square === square && fading.piece === pieceKey;

  return Object.fromEntries(
    (["w", "b"] as const).flatMap((color) =>
      Object.entries(PIECE_NAMES).map(([code, name]) => {
        const pieceKey = `${color}${code}` as Piece;
        const src = `/pieces/${color === "w" ? "White" : "Black"}-${name}.png`;
        return [
          pieceKey,
          ({ squareWidth, square }: { squareWidth: number; square?: Square }) => (
            // Keyed by code so the arriving capturer gets a fresh element instead
            // of inheriting its victim's. react-chessboard renders the piece
            // unkeyed inside its square, so React otherwise reuses the same <img>
            // and only swaps src -- leaving the capturer on the faded-out node,
            // fading in from nothing just as it lands.
            <img
              key={pieceKey}
              src={src}
              alt={pieceKey}
              draggable={false}
              style={{
                width: squareWidth,
                height: squareWidth,
                opacity: isFading(pieceKey, square) ? 0 : 1,
                transition: `opacity ${ANIMATION_MS}ms ease-out`,
              }}
            />
          ),
        ];
      })
    )
  ) as CustomPieces;
}

interface ReviewBoardProps {
  fen: string;
  flipped?: boolean;
  lastMoveUci?: string | null;
  arrowUci?: string | null;
  badge?: Classification | null;
  boardWidth?: number;
  onPieceDrop?: (source: string, target: string) => boolean;
  interactive?: boolean;
}

function parseUci(uci: string | null | undefined): [Square, Square] | null {
  if (!uci || uci.length < 4) return null;
  return [uci.slice(0, 2) as Square, uci.slice(2, 4) as Square];
}

export default function ReviewBoard({
  fen,
  flipped = false,
  lastMoveUci,
  arrowUci,
  badge,
  boardWidth = 520,
  onPieceDrop,
  interactive = false,
}: ReviewBoardProps) {
  const last = parseUci(lastMoveUci);
  const arrow = parseUci(arrowUci);
  const [fromSquare, toSquare] = last ?? [null, null];

  // Selection is board-local UI state. It must drop the moment the shown
  // position changes from outside — arrows, the sidebar, the nav buttons — and
  // a move played here changes `fen` too, so this covers "the move completes".
  const [selected, setSelected] = useState<Square | null>(null);
  useEffect(() => setSelected(null), [fen]);

  // Worked out during render rather than in an effect: the board reads
  // animationDuration inside its own position effect, and child effects run
  // first, so anything set from here afterwards would arrive a move too late.
  //
  // `epoch` bumps on every change that must not animate, remounting the board so
  // it takes its position straight from the prop. animationDuration={0} alone is
  // not enough: the board still runs its diffing branch, so pieces are briefly
  // transformed towards the squares that mis-pairing picked for them.
  const prevFen = useRef<string | null>(null);
  const transition = useRef<{ duration: number; fading: FadingPiece | null; epoch: number }>({
    duration: 0,
    fading: null,
    epoch: 0,
  });
  if (prevFen.current !== fen) {
    const before = prevFen.current;
    prevFen.current = fen;
    const { epoch } = transition.current;
    transition.current =
      before && isOnePly(before, fen)
        ? { duration: ANIMATION_MS, fading: capturedPiece(before, fen), epoch }
        : { duration: 0, fading: null, epoch: epoch + 1 };
  }
  const { duration, fading, epoch } = transition.current;

  const customPieces = useMemo(() => buildPieces(fading), [fading?.square, fading?.piece]);

  /**
   * Squares the selected piece may legally reach, tagged for how each draws: an
   * occupied destination is a capture (ring), an empty one a quiet move (dot).
   * En passant lands on an empty square, so it reads as a dot — matching the
   * reference. Generation runs on the current position, so this is identical on
   * the main line and inside an off-book branch. null means nothing selected.
   */
  const legalTargets = useMemo(() => {
    if (!selected) return null;
    try {
      const chess = new Chess(fen);
      const targets: Record<string, "dot" | "ring"> = {};
      for (const move of chess.moves({ square: selected, verbose: true })) {
        targets[move.to] = chess.get(move.to) ? "ring" : "dot";
      }
      return targets;
    } catch {
      return {};
    }
  }, [selected, fen]);

  /**
   * All 64 squares carry a colour and a transition, not just the highlighted
   * two. customSquareStyles renders onto an inner div that is only styled while
   * the map holds an entry for it, so dropping a square would cut its outgoing
   * highlight instead of fading it. Legal-move hints ride on backgroundImage so
   * they layer over the tint and appear without the background-color fade.
   */
  const customSquareStyles = useMemo(() => {
    const styles: Record<string, React.CSSProperties> = {};
    for (const file of "abcdefgh") {
      for (let rank = 1; rank <= 8; rank += 1) {
        const square = `${file}${rank}`;
        const hint = legalTargets?.[square];
        styles[square] = {
          // Selection wins over the last-move tint on a shared square.
          backgroundColor:
            square === selected
              ? SELECTED_SQUARE_BG
              : square === fromSquare
                ? LAST_MOVE_FROM
                : square === toSquare
                  ? LAST_MOVE_TO
                  : "transparent",
          backgroundImage: hint === "ring" ? LEGAL_RING : hint === "dot" ? LEGAL_DOT : "none",
          transition: `background-color ${ANIMATION_MS}ms ease-out`,
        };
      }
    }
    return styles;
  }, [fromSquare, toSquare, selected, legalTargets]);

  const arrows = arrow
    ? [[arrow[0], arrow[1], "rgba(17, 119, 45, 0.75)"] as [Square, Square, string]]
    : [];

  const badgeSquare = last?.[1];
  const badgeColor = badge ? BADGE_COLORS[badge] : undefined;

  // Only the side to move can be picked up — the enemy's pieces generate no
  // legal moves from this position, so selecting them would just show a bare
  // green square. chess.js's own turn is the source of truth via the FEN.
  const sideToMove = fen.split(" ")[1] === "b" ? "b" : "w";
  const isOwnPiece = (piece?: Piece) => !!piece && piece[0] === sideToMove;

  const handleSquareClick = (square: Square, piece?: Piece) => {
    if (!interactive) return;
    if (selected) {
      if (square === selected) {
        setSelected(null); // same piece again → toggle the selection off
      } else if (legalTargets?.[square]) {
        onPieceDrop?.(selected, square); // click-to-move; the position change clears the rest
        setSelected(null);
      } else if (isOwnPiece(piece)) {
        setSelected(square); // straight to another of our pieces
      } else {
        setSelected(null); // empty or enemy non-target → just deselect
      }
      return;
    }
    if (isOwnPiece(piece)) setSelected(square);
  };

  const handleDragBegin = (piece: Piece, sourceSquare: Square) => {
    if (interactive && isOwnPiece(piece)) setSelected(sourceSquare);
  };

  // A drag always ends the selection: a landed move changes `fen` (which clears
  // it regardless), while a snapback or a drop back on the origin leaves the
  // board unchanged and nothing selected.
  const handleDragEnd = () => setSelected(null);

  return (
    <div className="relative" style={{ width: boardWidth }}>
      <Chessboard
        key={epoch}
        position={fen}
        boardOrientation={flipped ? "black" : "white"}
        boardWidth={boardWidth}
        customSquareStyles={customSquareStyles}
        customArrows={arrows}
        customPieces={customPieces}
        animationDuration={duration}
        arePiecesDraggable={interactive}
        autoPromoteToQueen
        onPieceDrop={onPieceDrop}
        onSquareClick={handleSquareClick}
        onPieceDragBegin={handleDragBegin}
        onPieceDragEnd={handleDragEnd}
        customBoardStyle={{
          borderRadius: 5,
          boxShadow: "0 8px 30px rgba(0,0,0,0.35)",
        }}
        customDarkSquareStyle={{ backgroundColor: "#B98763" }}
        customLightSquareStyle={{ backgroundColor: "#EDD6B1" }}
      />
      {badge && badgeSquare && badgeColor && (
        <div
          key={`${badgeSquare}-${badge}`}
          className="board-badge-pop absolute z-10 pointer-events-none"
          style={{
            width: 28,
            height: 28,
            top: squareTop(badgeSquare, flipped, boardWidth) - 8,
            left: squareLeft(badgeSquare, flipped, boardWidth) + squareSize(boardWidth) - 20,
          }}
        >
          <img
            src={iconUrl(badge)}
            alt={badge}
            className="w-7 h-7 drop-shadow-md"
            title={badge}
          />
        </div>
      )}
    </div>
  );
}

/** FEN placement field -> { e4: "wP" }, using react-chessboard's piece codes. */
function boardMap(fen: string): Record<string, string> {
  const placement: Record<string, string> = {};
  fen.split(" ")[0].split("/").forEach((row, index) => {
    let file = 0;
    for (const ch of row) {
      const empty = Number(ch);
      if (empty) {
        file += empty;
        continue;
      }
      const square = `${String.fromCharCode(97 + file)}${8 - index}`;
      placement[square] = (ch === ch.toUpperCase() ? "w" : "b") + ch.toUpperCase();
      file += 1;
    }
  });
  return placement;
}

/** Whether one legal move from `before` produces `after`'s placement. */
function reaches(before: string, after: string): boolean {
  const target = after.split(" ")[0];
  try {
    return new Chess(before).moves({ verbose: true }).some((m) => m.after.split(" ")[0] === target);
  } catch {
    return false;
  }
}

/**
 * Whether two positions are a single move apart, in either direction.
 *
 * Only single-ply changes are safe to animate. react-chessboard pairs vacated
 * squares with occupied ones by piece code, so a multi-move diff -- clicking
 * straight to move 20, or jumping to the end -- slides pieces to squares they
 * never visited. Those have to snap.
 */
function isOnePly(before: string, after: string): boolean {
  return reaches(before, after) || reaches(after, before);
}

/**
 * The piece about to leave the board, if this move captures.
 *
 * react-chessboard glides the capturing piece but simply unmounts the captured
 * one once the animation ends, which is the pop this fades out instead. Finding
 * it is the library's own pairing inverted: a vacated square whose piece turns
 * up nowhere is not going anywhere. Promotions are excluded so the promoting
 * pawn isn't mistaken for a casualty.
 */
function capturedPiece(before: string, after: string): FadingPiece | null {
  const prev = boardMap(before);
  const next = boardMap(after);
  const arrived = Object.keys(next)
    .filter((square) => prev[square] !== next[square])
    .map((square) => next[square]);

  const gone = Object.keys(prev).filter((square) => {
    const piece = prev[square];
    if (next[square] === piece || arrived.includes(piece)) return false;
    return !(piece[1] === "P" && arrived.some((code) => code[0] === piece[0]));
  });

  return gone.length === 1 ? { square: gone[0], piece: prev[gone[0]] } : null;
}

function squareSize(boardWidth: number) {
  return boardWidth / 8;
}

function squareLeft(square: string, flipped: boolean, boardWidth: number) {
  const file = square.charCodeAt(0) - 97;
  const size = squareSize(boardWidth);
  const col = flipped ? 7 - file : file;
  return col * size;
}

function squareTop(square: string, flipped: boolean, boardWidth: number) {
  const rank = parseInt(square[1], 10) - 1;
  const size = squareSize(boardWidth);
  const row = flipped ? rank : 7 - rank;
  return row * size;
}
