import { act, render, screen } from "@testing-library/react";
import type { CSSProperties } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReviewBoard from "./ReviewBoard";

interface ChessboardProps {
  boardOrientation: "white" | "black";
  customSquareStyles: Record<string, CSSProperties>;
  onPieceDrop?: (source: string, target: string) => boolean;
  onSquareClick?: (square: string, piece?: string) => void;
}

const board = vi.hoisted(() => ({ current: null as ChessboardProps | null }));

vi.mock("react-chessboard", () => ({
  Chessboard: (props: ChessboardProps) => {
    board.current = props;
    return <div data-testid="chessboard" />;
  },
}));

const AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1";

describe("ReviewBoard orientation", () => {
  beforeEach(() => {
    board.current = null;
  });

  it("flips pieces and coordinates while keeping square overlays coordinate-based", () => {
    const onPieceDrop = vi.fn(() => true);
    const { rerender } = render(
      <ReviewBoard
        fen={AFTER_E4}
        flipped={false}
        lastMoveUci="e2e4"
        interactive
        onPieceDrop={onPieceDrop}
      />
    );

    expect(board.current?.boardOrientation).toBe("white");
    const whiteStyles = board.current?.customSquareStyles;
    expect(whiteStyles?.e2.backgroundColor).not.toBe("transparent");
    expect(whiteStyles?.e4.backgroundColor).not.toBe("transparent");

    rerender(
      <ReviewBoard
        fen={AFTER_E4}
        flipped
        lastMoveUci="e2e4"
        interactive
        onPieceDrop={onPieceDrop}
      />
    );

    expect(board.current?.boardOrientation).toBe("black");
    expect(board.current?.customSquareStyles.e2).toEqual(whiteStyles?.e2);
    expect(board.current?.customSquareStyles.e4).toEqual(whiteStyles?.e4);
    expect(board.current?.onPieceDrop).toBe(onPieceDrop);
  });

  it("keeps selection, legal targets, and click-to-move on algebraic squares when flipped", () => {
    const onPieceDrop = vi.fn(() => true);
    render(<ReviewBoard fen={AFTER_E4} flipped interactive onPieceDrop={onPieceDrop} />);

    act(() => board.current?.onSquareClick?.("e7", "bP"));
    expect(board.current?.customSquareStyles.e7.backgroundColor).not.toBe("transparent");
    expect(board.current?.customSquareStyles.e5.backgroundImage).toContain("radial-gradient");
    expect(board.current?.customSquareStyles.e6.backgroundImage).toContain("radial-gradient");

    act(() => board.current?.onSquareClick?.("e5"));
    expect(onPieceDrop).toHaveBeenCalledWith("e7", "e5");
  });

  it("repositions the coordinate-dependent badge after a flip", () => {
    const { rerender } = render(
      <ReviewBoard fen={AFTER_E4} flipped={false} lastMoveUci="e2e4" badge="Best" boardWidth={800} />
    );
    const badge = screen.getByAltText("Best").parentElement;
    expect(badge).toHaveStyle({ left: "480px", top: "392px" });

    rerender(
      <ReviewBoard fen={AFTER_E4} flipped lastMoveUci="e2e4" badge="Best" boardWidth={800} />
    );
    expect(screen.getByAltText("Best").parentElement).toHaveStyle({ left: "380px", top: "292px" });
  });
});
