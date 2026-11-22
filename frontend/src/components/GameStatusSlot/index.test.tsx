import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { GamePreview } from "../../pgnPreview";
import GameStatusSlot from "./index";

vi.mock("react-chessboard", () => ({
  Chessboard: ({ position }: { position: string }) => (
    <div data-testid="status-board" data-position={position} />
  ),
}));

const preview: GamePreview = {
  sourcePgn: "1. e4 e5",
  white: "Alice",
  black: "Bob",
  result: "1-0",
  resultLabel: "1–0",
  opening: "King's Pawn Game",
  eco: "C20",
  date: "22 Nov 2026",
  event: "Casual",
  moveCount: 1,
  termination: "checkmate",
  fen: "test-fen",
  uciMoves: ["e2e4", "e7e5"],
};

describe("GameStatusSlot", () => {
  it("renders empty and invalid parse states", () => {
    const { rerender } = render(<GameStatusSlot state={{ kind: "empty" }} />);
    expect(screen.getByText("Paste a PGN to preview the game")).toBeInTheDocument();

    rerender(<GameStatusSlot state={{ kind: "invalid", reason: "Illegal move" }} />);
    expect(screen.getByText("Couldn't read this game")).toBeInTheDocument();
    expect(screen.getByText("Illegal move")).toBeInTheDocument();
  });

  it("renders preview metadata and running progress", () => {
    render(
      <GameStatusSlot
        state={{ kind: "running", preview, progress: { ply: 1, total: 2 } }}
      />
    );

    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("King's Pawn Game")).toBeInTheDocument();
    expect(screen.getByText("Analyzing move 1 of 2")).toBeInTheDocument();
    expect(screen.getByTestId("status-board")).toHaveAttribute("data-position", "test-fen");
  });

  it("distinguishes completed Gemini success from coaching fallback", () => {
    const { rerender } = render(
      <GameStatusSlot
        state={{ kind: "completed", preview, commentarySucceeded: false }}
      />
    );
    expect(screen.getByText("Review complete — coaching fallback used")).toBeInTheDocument();

    rerender(
      <GameStatusSlot
        state={{
          kind: "completed",
          preview,
          commentarySucceeded: false,
          commentaryStatus: {
            gemini_attempted: true,
            generation_complete: true,
            summary_generated: true,
            summary_accepted: false,
            requested_comments: 1,
            generated_comments: 1,
            accepted_comments: 0,
            fallback_used: true,
          },
        }}
      />
    );
    expect(screen.getByText("Status: Success")).toBeInTheDocument();
  });
});
