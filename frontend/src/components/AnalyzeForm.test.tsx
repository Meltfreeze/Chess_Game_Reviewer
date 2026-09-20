import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchHealth } from "../api/client";
import AnalyzeForm from "./AnalyzeForm";

vi.mock("../api/client", () => ({
  fetchHealth: vi.fn(),
}));

vi.mock("react-chessboard", () => ({
  Chessboard: ({ position }: { position: string }) => (
    <div data-testid="mini-board" data-position={position} />
  ),
}));

const mockedFetchHealth = vi.mocked(fetchHealth);

describe("AnalyzeForm depth selector", () => {
  beforeEach(() => {
    mockedFetchHealth.mockResolvedValue({ ready: true, gemini_configured: true });
  });

  it("uses an integer depth range from 8 through 22", () => {
    render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);

    const slider = screen.getByRole("slider", { name: "Analysis depth" });

    expect(slider).toHaveAttribute("min", "8");
    expect(slider).toHaveAttribute("max", "22");
    expect(slider).toHaveAttribute("step", "1");
    expect(slider).toHaveValue("16");
    expect(screen.getByText("Balanced")).toHaveClass("text-accent");
  });

  it("does not ask for a player color", () => {
    render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);

    expect(screen.queryByText("Playing as")).not.toBeInTheDocument();
    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
  });

  it("shows the empty preview slot and disables review", () => {
    render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);

    expect(screen.getByText("Paste a PGN to preview the game")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review Game" })).toBeDisabled();
    expect(screen.getByTitle("Paste a valid PGN first")).toBeInTheDocument();
  });

  it("passes the displayed slider depth to onAnalyze", async () => {
    const onAnalyze = vi.fn();
    render(<AnalyzeForm onAnalyze={onAnalyze} loading={false} />);

    const slider = screen.getByRole("slider", { name: "Analysis depth" });
    fireEvent.change(slider, { target: { value: "19" } });

    expect(slider).toHaveValue("19");
    expect(screen.getByText("Deep")).toHaveClass("text-accent");

    fireEvent.change(screen.getByRole("textbox", { name: "PGN" }), {
      target: { value: "1. e4 e5" },
    });
    await waitFor(() => expect(screen.getByRole("button", { name: "Review Game" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Review Game" }));

    expect(onAnalyze).toHaveBeenCalledWith("1. e4 e5", 19);
  });

  it("previews a valid game and derives its result and termination", async () => {
    render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);
    fireEvent.change(screen.getByRole("textbox", { name: "PGN" }), {
      target: {
        value: `[Event "Casual Game"]
[Date "2026.08.29"]
[White "Scholar"]
[Black "Opponent"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0`,
      },
    });

    expect(await screen.findByText("PGN valid")).toBeInTheDocument();
    expect(screen.getByText("Scholar")).toBeInTheDocument();
    expect(screen.getByText("Opponent")).toBeInTheDocument();
    expect(screen.getByText("Scholar").parentElement).toHaveClass("max-w-[35%]");
    expect(screen.getByText("Opponent").parentElement).toHaveClass("max-w-[35%]");
    expect(screen.getByText("1–0")).toBeInTheDocument();
    expect(screen.getByText(/29 Aug 2026 · 4 moves · Casual Game · checkmate/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /checkmate/ })).toBeInTheDocument();
  });

  it("shows a specific invalid-move reason and keeps review disabled", async () => {
    render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);
    fireEvent.change(screen.getByRole("textbox", { name: "PGN" }), {
      target: { value: "1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf5" },
    });

    expect(await screen.findByText("Couldn't read this game")).toBeInTheDocument();
    expect(screen.getByText(/Move 3 \(Nf5\) isn't legal/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review Game" })).toBeDisabled();
  });

  it("rejects multiple games and never submits stale valid state", async () => {
    const onAnalyze = vi.fn();
    render(<AnalyzeForm onAnalyze={onAnalyze} loading={false} />);
    const input = screen.getByRole("textbox", { name: "PGN" });
    fireEvent.change(input, { target: { value: "1. e4 e5 1-0" } });
    expect(await screen.findByText("PGN valid")).toBeInTheDocument();

    const multiple = `[Event "One"]

1. e4 e5 1-0

[Event "Two"]

1. d4 d5 0-1`;
    fireEvent.change(input, { target: { value: multiple } });

    const button = screen.getByRole("button", { name: "Review Game" });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onAnalyze).not.toHaveBeenCalled();
    expect(await screen.findByText("This PGN contains 2 games. Paste one game at a time.")).toBeInTheDocument();
    expect(screen.queryByText(/Game 1 of/)).not.toBeInTheDocument();
  });

  it.each([
    [12, "Quick"],
    [13, "Balanced"],
    [17, "Balanced"],
    [18, "Deep"],
  ])("highlights the correct depth band at depth %i", (depth, band) => {
    render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);
    const slider = screen.getByRole("slider", { name: "Analysis depth" });

    fireEvent.change(slider, { target: { value: String(depth) } });

    expect(screen.getByText(band)).toHaveClass("text-accent");
  });

  it("reads a PGN dropped onto the input", async () => {
    render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);
    const dropZone = screen.getByTestId("pgn-drop-zone");
    const file = {
      name: "game.pgn",
      text: vi.fn().mockResolvedValue("1. d4 d5 2. c4"),
    } as unknown as File;

    fireEvent.dragOver(dropZone, { dataTransfer: { files: [file], dropEffect: "none" } });
    expect(dropZone).toHaveClass("border-accent");

    fireEvent.drop(dropZone, { dataTransfer: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: "PGN" })).toHaveValue("1. d4 d5 2. c4");
      expect(screen.getByRole("button", { name: "Review Game" })).toBeEnabled();
    });
    expect(file.text).toHaveBeenCalledOnce();
  });

  it("allows analysis with verified fallback coaching when Gemini is unavailable", async () => {
    mockedFetchHealth.mockResolvedValue({ ready: true, gemini_configured: false });
    render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);

    fireEvent.change(screen.getByRole("textbox", { name: "PGN" }), {
      target: { value: "1. e4 e5" },
    });

    await waitFor(() => expect(screen.getByRole("button", { name: "Review Game" })).toBeEnabled());
    expect(screen.getByText(/verified fallback coaching/i)).toBeInTheDocument();
  });

  it("locks inputs and shows progress while analysis is running", async () => {
    const { rerender } = render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);
    fireEvent.change(screen.getByRole("textbox", { name: "PGN" }), {
      target: { value: "1. e4 e5" },
    });
    expect(await screen.findByText("PGN valid")).toBeInTheDocument();

    rerender(<AnalyzeForm onAnalyze={vi.fn()} loading progress={{ ply: 1, total: 2 }} />);

    expect(screen.getByText("Analyzing")).toBeInTheDocument();
    expect(screen.getByText("Analyzing move 1 of 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reviewing…" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "PGN" })).toHaveAttribute("readonly");
    expect(screen.getByRole("slider", { name: "Analysis depth" })).toBeDisabled();
  });

  it("keeps the preview and shows a retryable failure", async () => {
    const pgn = "1. e4 e5";
    const { rerender } = render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);
    fireEvent.change(screen.getByRole("textbox", { name: "PGN" }), {
      target: { value: pgn },
    });
    expect(await screen.findByText("PGN valid")).toBeInTheDocument();

    rerender(
      <AnalyzeForm
        onAnalyze={vi.fn()}
        loading={false}
        analysisFailure={{ kind: "timeout", pgn, depth: 16 }}
      />
    );

    expect(screen.getByText("Review failed")).toBeInTheDocument();
    expect(screen.getByText("The analysis timed out at depth 16. Try a lower depth.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review Game" })).toBeEnabled();
  });

  it.each([
    [true, "Status: Success"],
    [false, "Status: Failure"],
  ])("shows review completion and its commentary mode", async (commentarySucceeded, message) => {
    const pgn = "1. e4 e5";
    const { rerender } = render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);
    fireEvent.change(screen.getByRole("textbox", { name: "PGN" }), {
      target: { value: pgn },
    });
    expect(await screen.findByText("PGN valid")).toBeInTheDocument();

    rerender(
      <AnalyzeForm
        onAnalyze={vi.fn()}
        loading={false}
        analysisCompletion={{ pgn, commentarySucceeded }}
      />
    );

    expect(screen.getByText("Review complete")).toBeInTheDocument();
    expect(screen.getByText(message)).toBeInTheDocument();
  });

  it("reports Gemini success when complete output was returned but verification replaced text", async () => {
    const pgn = "1. e4 e5";
    const { rerender } = render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);
    fireEvent.change(screen.getByRole("textbox", { name: "PGN" }), {
      target: { value: pgn },
    });
    expect(await screen.findByText("PGN valid")).toBeInTheDocument();

    rerender(
      <AnalyzeForm
        onAnalyze={vi.fn()}
        loading={false}
        analysisCompletion={{
          pgn,
          commentarySucceeded: false,
          commentaryStatus: {
            gemini_attempted: true,
            generation_complete: true,
            summary_generated: true,
            summary_accepted: false,
            requested_comments: 2,
            generated_comments: 2,
            accepted_comments: 2,
            fallback_used: true,
          },
        }}
      />
    );

    expect(screen.getByText("Status: Success")).toBeInTheDocument();
  });

  it("keeps the Stockfish health warning", async () => {
    mockedFetchHealth.mockResolvedValue({
      ready: false,
      error: "binary missing",
      gemini_configured: true,
    });
    render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);

    expect(await screen.findByText("Stockfish not ready: binary missing")).toBeInTheDocument();
  });

  it("does not render the old detached status line", () => {
    render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);
    expect(screen.queryByText(/^Status:/)).not.toBeInTheDocument();
  });
});
