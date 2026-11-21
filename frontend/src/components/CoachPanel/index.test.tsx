import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CoachPanel from "./index";

describe("CoachPanel", () => {
  it("shows the move classification, comment, and best line", () => {
    render(
      <CoachPanel
        summary="Game summary"
        comment="The move wins material."
        classification="Best"
        bestLine={["Nf3", "Nc6"]}
      />
    );

    expect(screen.getByText("Best")).toBeInTheDocument();
    expect(screen.getByText("The move wins material.")).toBeInTheDocument();
    expect(screen.getByText(/Nf3 Nc6/)).toBeInTheDocument();
  });

  it("prioritizes loading and error states over coaching prose", () => {
    const { rerender } = render(
      <CoachPanel summary="Summary" comment="Comment" loading error="Failed" />
    );
    expect(screen.getByText("Looking at this move…")).toBeInTheDocument();
    expect(screen.queryByText("Comment")).not.toBeInTheDocument();

    rerender(<CoachPanel summary="Summary" comment="Comment" error="Failed" />);
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.queryByText("Comment")).not.toBeInTheDocument();
  });
});
