import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AnalysisResult } from "./types";
import App from "./App";

const appView = vi.hoisted(() => ({
  analyzedColor: "White" as "White" | "Black",
}));

vi.mock("./components/AnalyzeForm", () => ({
  default: ({ onAnalyze }: { onAnalyze: (pgn: string, color: "White" | "Black", depth: number) => void }) => (
    <button type="button" onClick={() => onAnalyze("fixture", appView.analyzedColor, 16)}>
      Analyze fixture
    </button>
  ),
}));

vi.mock("./components/ReviewBoard", () => ({
  default: ({ flipped, fen }: { flipped: boolean; fen: string }) => (
    <div data-testid="review-board" data-flipped={flipped} data-fen={fen} />
  ),
}));

vi.mock("./components/MoveNav", () => ({
  default: ({ onFlip, onFirst }: { onFlip: () => void; onFirst: () => void }) => (
    <>
      <button type="button" onClick={onFlip}>Flip board</button>
      <button type="button" onClick={onFirst}>First move</button>
    </>
  ),
}));

vi.mock("./components/EvalBar", () => ({
  default: ({ flipped }: { flipped: boolean }) => (
    <div data-testid="eval-bar" data-flipped={flipped} />
  ),
}));
vi.mock("./components/ReviewSidebar", () => ({ default: () => null }));
vi.mock("./components/VariationBanner", () => ({ default: () => null }));
vi.mock("./components/PasswordModal", () => ({ default: () => null }));
vi.mock("./api/auth", () => ({
  AuthError: class AuthError extends Error {},
  hasValidToken: () => true,
}));
vi.mock("./api/client", () => ({
  analyzeGame: vi.fn(),
  reviewMove: vi.fn(),
}));

import { analyzeGame } from "./api/client";

const RESULT: AnalysisResult = {
  move_data: [
    {
      ply: 1,
      move_number: 1,
      turn: "White",
      san: "e4",
      uci: "e2e4",
      fen: "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
      fen_before: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      eval: "+0.2",
      eval_cp_white: 20,
      classification: "Best",
      facts: {
        played: "e4",
        class: "Best",
        eval_before: 0,
        eval_after: 20,
      },
      prompt_str: "",
      cp_loss: 0,
      best_line: [],
      best_uci: "e2e4",
      best_move: "e2e4",
      played_move: "e2e4",
      best_wp: 0.53,
      second_best_wp: 0.5,
      legal_move_count: 20,
      eval_swing: 20,
      phase: "opening",
    },
  ],
  stats: {
    White: { rating: 1200, acpl: 0, accuracy: 100 },
    Black: { rating: 1200, acpl: 0, accuracy: 100 },
  },
  meta: { White: "White", Black: "Black", WhiteElo: "1200", BlackElo: "1200", Result: "*" },
  hist: [20],
  critical_moments: [],
  coach: { summary: "", comments: [""] },
  player_color: "White",
};

describe("App board orientation", () => {
  beforeEach(() => {
    appView.analyzedColor = "White";
    vi.mocked(analyzeGame).mockResolvedValue(RESULT);
  });

  it("keeps the flipped orientation while navigating moves", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Analyze fixture" }));
    await waitFor(() => expect(screen.getByTestId("review-board")).toHaveAttribute("data-flipped", "false"));
    expect(screen.getByTestId("eval-bar")).toHaveAttribute("data-flipped", "false");

    fireEvent.click(screen.getByRole("button", { name: "Flip board" }));
    expect(screen.getByTestId("review-board")).toHaveAttribute("data-flipped", "true");
    expect(screen.getByTestId("eval-bar")).toHaveAttribute("data-flipped", "true");

    fireEvent.click(screen.getByRole("button", { name: "First move" }));
    expect(screen.getByTestId("review-board")).toHaveAttribute("data-flipped", "true");

    fireEvent.click(screen.getByRole("button", { name: "Flip board" }));
    expect(screen.getByTestId("review-board")).toHaveAttribute("data-flipped", "false");
    expect(screen.getByTestId("eval-bar")).toHaveAttribute("data-flipped", "false");
  });

  it("starts a new review from the analyzed player's perspective", async () => {
    appView.analyzedColor = "Black";
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Analyze fixture" }));

    await waitFor(() => expect(screen.getByTestId("review-board")).toHaveAttribute("data-flipped", "true"));
  });
});
