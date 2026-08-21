import { Chessboard } from "react-chessboard";
import type { Square } from "react-chessboard/dist/chessboard/types";
import type { Classification } from "../types";
import { iconUrl } from "../api/client";

const BADGE_COLORS: Record<string, string> = {
  Brilliant: "#1BADA6",
  Great: "#5C8BB0",
  Best: "#95BB4A",
  Excellent: "#95BB4A",
  Good: "#96AF8B",
  Book: "#A88865",
  Inaccuracy: "#F0C15C",
  Miss: "#EE6B55",
  Mistake: "#E58F2A",
  Blunder: "#CA3431",
};

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

  const customSquareStyles: Record<string, React.CSSProperties> = {};
  if (last) {
    customSquareStyles[last[0]] = { background: "rgba(246, 246, 105, 0.72)" };
    customSquareStyles[last[1]] = { background: "rgba(186, 202, 43, 0.72)" };
  }

  const arrows = arrow
    ? [[arrow[0], arrow[1], "rgba(17, 119, 45, 0.75)"] as [Square, Square, string]]
    : [];

  const badgeSquare = last?.[1];
  const badgeColor = badge ? BADGE_COLORS[badge] : undefined;

  return (
    <div className="relative" style={{ width: boardWidth }}>
      <Chessboard
        position={fen}
        boardOrientation={flipped ? "black" : "white"}
        boardWidth={boardWidth}
        customSquareStyles={customSquareStyles}
        customArrows={arrows}
        arePiecesDraggable={interactive}
        onPieceDrop={onPieceDrop}
        customBoardStyle={{
          borderRadius: 5,
          boxShadow: "0 8px 30px rgba(0,0,0,0.35)",
        }}
        customDarkSquareStyle={{ backgroundColor: "#779556" }}
        customLightSquareStyle={{ backgroundColor: "#EBECD0" }}
      />
      {badge && badgeSquare && badgeColor && (
        <div
          className="absolute z-10 pointer-events-none"
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
