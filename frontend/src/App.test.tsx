import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AnalysisCompletion, AnalysisFailure, AnalysisResult } from "./types";
import App from "./App";

vi.mock("./components/AnalyzeForm", () => ({
  default: ({
    onAnalyze,
    analysisFailure,
    analysisCompletion,
  }: {
    onAnalyze: (pgn: string, depth: number) => void;
    analysisFailure: AnalysisFailure | null;
    analysisCompletion: AnalysisCompletion | null;
  }) => (
    <>
      <button type="button" onClick={() => onAnalyze("fixture", 16)}>
        Analyze fixture
      </button>
      {analysisFailure && (
        <span data-testid="analysis-failure">{analysisFailure.kind}</span>
      )}
      {analysisCompletion && (
        <span data-testid="analysis-completion">
          {analysisCompletion.commentarySucceeded
            ? "ai"
            : analysisCompletion.commentaryStatus?.generation_complete
              ? "generated-rejected"
              : "fallback"}
        </span>
      )}
    </>
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
  commentary_succeeded: true,
};

describe("App board orientation", () => {
  beforeEach(() => {
    vi.mocked(analyzeGame).mockReset();
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

  it("starts every new review with White at the bottom", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Analyze fixture" }));
    await waitFor(() => expect(screen.getByTestId("review-board")).toHaveAttribute("data-flipped", "false"));

    fireEvent.click(screen.getByRole("button", { name: "Flip board" }));
    expect(screen.getByTestId("review-board")).toHaveAttribute("data-flipped", "true");

    fireEvent.click(screen.getByRole("button", { name: "Analyze fixture" }));

    await waitFor(() => expect(screen.getByTestId("review-board")).toHaveAttribute("data-flipped", "false"));
  });

  it("classifies a timeout for the preview slot and clears it on retry", async () => {
    let finishSecondRun: (result: AnalysisResult) => void = () => {};
    const secondRun = new Promise<AnalysisResult>((resolve) => {
      finishSecondRun = resolve;
    });
    vi.mocked(analyzeGame)
      .mockRejectedValueOnce(new Error("Engine timeout"))
      .mockReturnValueOnce(secondRun);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Analyze fixture" }));
    await waitFor(() => {
      expect(screen.getByTestId("analysis-failure")).toHaveTextContent("timeout");
    });
    expect(consoleError).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Analyze fixture" }));
    expect(screen.queryByTestId("analysis-failure")).not.toBeInTheDocument();

    finishSecondRun(RESULT);
    await waitFor(() => {
      expect(screen.queryByTestId("analysis-failure")).not.toBeInTheDocument();
      expect(screen.getByTestId("analysis-completion")).toHaveTextContent("ai");
    });
    consoleError.mockRestore();
  });

  it("reports fallback commentary separately from review completion", async () => {
    vi.mocked(analyzeGame).mockResolvedValue({ ...RESULT, commentary_succeeded: false });

    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Analyze fixture" }));

    await waitFor(() => {
      expect(screen.getByTestId("analysis-completion")).toHaveTextContent("fallback");
    });
  });

  it("passes through complete Gemini output that failed verification", async () => {
    vi.mocked(analyzeGame).mockResolvedValue({
      ...RESULT,
      commentary_succeeded: false,
      commentary_status: {
        gemini_attempted: true,
        generation_complete: true,
        summary_generated: true,
        summary_accepted: false,
        requested_comments: 1,
        generated_comments: 1,
        accepted_comments: 1,
        fallback_used: true,
      },
    });

    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Analyze fixture" }));

    await waitFor(() => {
      expect(screen.getByTestId("analysis-completion")).toHaveTextContent("generated-rejected");
    });
  });
});
