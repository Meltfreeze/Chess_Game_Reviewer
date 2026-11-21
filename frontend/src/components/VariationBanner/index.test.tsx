import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import VariationBanner from "./index";

describe("VariationBanner", () => {
  it("returns to the reviewed game when requested", () => {
    const onReturn = vi.fn();
    render(<VariationBanner onReturn={onReturn} />);

    expect(screen.getByText("Exploring a variation")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back to the game" }));
    expect(onReturn).toHaveBeenCalledOnce();
  });
});
