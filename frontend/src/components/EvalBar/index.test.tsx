import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import EvalBar from "./index";

describe("EvalBar orientation", () => {
  it("anchors White's fill and positive label at the bottom by default", () => {
    render(<EvalBar evalCpWhite={380} height={520} />);

    expect(screen.getByTestId("eval-bar-white-fill")).toHaveStyle({
      top: "auto",
      bottom: "0px",
    });
    expect(screen.getByText("3.8")).toHaveStyle({
      top: "auto",
      bottom: "3px",
    });
  });

  it("anchors White's fill and positive label at the top when flipped", () => {
    render(<EvalBar evalCpWhite={380} height={520} flipped />);

    expect(screen.getByTestId("eval-bar-white-fill")).toHaveStyle({
      top: "0px",
      bottom: "auto",
    });
    expect(screen.getByText("3.8")).toHaveStyle({
      top: "3px",
      bottom: "auto",
    });
  });

  it("places a Black-advantage label at Black's end in either orientation", () => {
    const { rerender } = render(<EvalBar evalCpWhite={-125} />);
    expect(screen.getByText("1.3")).toHaveStyle({ top: "3px", bottom: "auto" });

    rerender(<EvalBar evalCpWhite={-125} flipped />);
    expect(screen.getByText("1.3")).toHaveStyle({ top: "auto", bottom: "3px" });
  });
});
