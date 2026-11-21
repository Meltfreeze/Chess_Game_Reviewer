import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import EvalGraph from "./index";

describe("EvalGraph", () => {
  it("positions the cursor at the selected ply", () => {
    const { container } = render(<EvalGraph history={[0, 1, -1]} currentPly={1} />);
    const lines = container.querySelectorAll("line");

    expect(lines[1]).toHaveAttribute("x1", "50");
    expect(lines[1]).toHaveAttribute("x2", "50");
  });

  it("maps clicks to a clamped history ply", () => {
    const onSelect = vi.fn();
    const { container } = render(
      <EvalGraph history={[0, 1, 2, 3, 4]} currentPly={0} onSelect={onSelect} />
    );
    const graph = container.querySelector("svg")!;
    vi.spyOn(graph, "getBoundingClientRect").mockReturnValue({
      x: 10,
      y: 0,
      left: 10,
      top: 0,
      right: 210,
      bottom: 70,
      width: 200,
      height: 70,
      toJSON: () => ({}),
    });

    fireEvent.click(graph, { clientX: 160 });
    expect(onSelect).toHaveBeenCalledWith(3);
  });
});
