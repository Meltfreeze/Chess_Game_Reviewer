import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AnalysisResult, MoveData } from "../../types";
import GameSummary, { RatingFooter } from "./index";

const result = {
  move_data: [
    { classification: "Best", turn: "White" },
    { classification: "Blunder", turn: "Black" },
    { classification: "Best", turn: "Black" },
  ] as MoveData[],
  stats: {
    White: { accuracy: 97.25, rating: 1820, acpl: 12 },
    Black: { accuracy: 81.04, rating: 1640, acpl: 44 },
  },
  meta: { White: "Alice", Black: "Bob", WhiteElo: "", BlackElo: "", Result: "1-0" },
  hist: [],
  critical_moments: [],
  coach: { summary: "", comments: [] },
} satisfies AnalysisResult;

describe("GameSummary", () => {
  it("summarizes player accuracy and classification counts", () => {
    render(<GameSummary result={result} />);

    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("97.3")).toBeInTheDocument();
    expect(screen.getByText("81.0")).toBeInTheDocument();
    const bestRow = screen.getByText("Best").parentElement!;
    expect(bestRow).toHaveTextContent("Best11");
    const blunderRow = screen.getByText("Blunder").parentElement!;
    expect(blunderRow).toHaveTextContent("Blunder01");
  });

  it("shows both estimated performance ratings", () => {
    render(<RatingFooter result={result} />);

    expect(screen.getByText("1820")).toBeInTheDocument();
    expect(screen.getByText("1640")).toBeInTheDocument();
  });
});
