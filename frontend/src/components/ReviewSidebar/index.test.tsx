import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { MoveTree } from "../../moveTree";
import type { AnalysisResult } from "../../types";
import ReviewSidebar from "./index";

vi.mock("../CoachPanel", () => ({ default: () => <div>Coach content</div> }));
vi.mock("../EvalGraph", () => ({ default: () => <div>Evaluation graph</div> }));
vi.mock("../GameSummary", () => ({
  default: () => <div>Game summary</div>,
  RatingFooter: () => <div>Rating footer</div>,
}));
vi.mock("../MoveList", () => ({ default: () => <div>Move list</div> }));

const result = {
  move_data: [],
  stats: {
    White: { accuracy: 0, rating: 0, acpl: 0 },
    Black: { accuracy: 0, rating: 0, acpl: 0 },
  },
  meta: { White: "A", Black: "B", WhiteElo: "", BlackElo: "", Result: "*" },
  hist: [0],
  critical_moments: [],
  coach: { summary: "Summary", comments: [] },
} satisfies AnalysisResult;

const tree: MoveTree = {
  rootId: "root",
  currentId: "root",
  nodes: {
    root: {
      id: "root",
      parentId: null,
      childIds: [],
      lastActiveChildId: null,
      isMainLine: true,
      ply: 0,
      san: "",
      uci: "",
      fen: "",
      moveNumber: 0,
      turn: "White",
      data: null,
      comment: "",
      status: "ready",
      error: null,
    },
  },
};

describe("ReviewSidebar", () => {
  it("switches between review and move-list content", () => {
    render(
      <ReviewSidebar
        result={result}
        tree={tree}
        currentPly={0}
        onSelectPly={vi.fn()}
        onSelectNode={vi.fn()}
      />
    );

    expect(screen.getByText("Coach content")).toBeInTheDocument();
    expect(screen.getByText("Game summary")).toBeInTheDocument();
    expect(screen.getByText("Rating footer")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Moves" }));
    expect(screen.getByText("Move list")).toBeInTheDocument();
    expect(screen.queryByText("Rating footer")).not.toBeInTheDocument();
  });
});
