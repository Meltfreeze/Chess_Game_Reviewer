import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MoveNav from "./MoveNav";

function renderNav(overrides: Partial<React.ComponentProps<typeof MoveNav>> = {}) {
  const props: React.ComponentProps<typeof MoveNav> = {
    flipped: false,
    canPrev: true,
    canNext: true,
    canJumpEnd: true,
    onFlip: vi.fn(),
    onFirst: vi.fn(),
    onPrev: vi.fn(),
    onNext: vi.fn(),
    onLast: vi.fn(),
    ...overrides,
  };
  render(<MoveNav {...props} />);
  return props;
}

describe("MoveNav", () => {
  it("places the flip control before the four existing navigation buttons", () => {
    renderNav();

    expect(screen.getAllByRole("button").map((button) => button.getAttribute("aria-label"))).toEqual([
      "Flip board",
      "First move",
      "Previous move",
      "Next move",
      "Last move",
    ]);
  });

  it("reports and toggles the board orientation independently of navigation", () => {
    const onFlip = vi.fn();
    const { rerender } = render(
      <MoveNav
        flipped={false}
        canPrev
        canNext
        canJumpEnd
        onFlip={onFlip}
        onFirst={vi.fn()}
        onPrev={vi.fn()}
        onNext={vi.fn()}
        onLast={vi.fn()}
      />
    );

    const flipButton = screen.getByRole("button", { name: "Flip board" });
    expect(flipButton).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(flipButton);
    expect(onFlip).toHaveBeenCalledOnce();

    rerender(
      <MoveNav
        flipped
        canPrev
        canNext
        canJumpEnd
        onFlip={onFlip}
        onFirst={vi.fn()}
        onPrev={vi.fn()}
        onNext={vi.fn()}
        onLast={vi.fn()}
      />
    );
    expect(screen.getByRole("button", { name: "Flip board" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });
});
