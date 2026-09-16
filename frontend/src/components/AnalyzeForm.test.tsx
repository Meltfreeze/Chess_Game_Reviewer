import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchHealth } from "../api/client";
import AnalyzeForm from "./AnalyzeForm";

vi.mock("../api/client", () => ({
  fetchHealth: vi.fn(),
}));

const mockedFetchHealth = vi.mocked(fetchHealth);

describe("AnalyzeForm depth selector", () => {
  beforeEach(() => {
    mockedFetchHealth.mockResolvedValue({ ready: true, gemini_configured: true });
  });

  it("shows the preset depths and marks the active depth", () => {
    render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);

    fireEvent.click(screen.getByRole("button", { name: /current 14/i }));

    expect(screen.getAllByRole("option")).toHaveLength(5);
    expect(screen.getByRole("option", { name: /14/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("option", { name: /12/ })).toHaveAttribute("aria-selected", "false");
  });

  it("updates the existing depth used for analysis and closes after selection", async () => {
    const onAnalyze = vi.fn();
    render(<AnalyzeForm onAnalyze={onAnalyze} loading={false} />);

    fireEvent.click(screen.getByRole("button", { name: /current 14/i }));
    fireEvent.click(screen.getByRole("option", { name: /18/ }));

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /current 18/i })).toHaveTextContent("18");

    fireEvent.change(screen.getByPlaceholderText("Paste PGN here..."), {
      target: { value: "1. e4 e5" },
    });
    await waitFor(() => expect(screen.getByRole("button", { name: "Review Game" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Review Game" }));

    expect(onAnalyze).toHaveBeenCalledWith("1. e4 e5", "White", 18);
  });

  it("supports keyboard opening, navigation, selection, and Escape", () => {
    render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);
    const trigger = screen.getByRole("button", { name: /current 14/i });

    trigger.focus();
    fireEvent.keyDown(trigger, { key: "Enter" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.keyDown(trigger, { key: "Enter" });

    expect(screen.getByRole("button", { name: /current 16/i })).toHaveFocus();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();

    fireEvent.keyDown(screen.getByRole("button", { name: /current 16/i }), { key: " " });
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("closes when clicking outside the control", () => {
    render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);

    fireEvent.click(screen.getByRole("button", { name: /current 14/i }));
    fireEvent.mouseDown(screen.getByText("Analyze a new game"));

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("allows analysis with verified fallback coaching when Gemini is unavailable", async () => {
    mockedFetchHealth.mockResolvedValue({ ready: true, gemini_configured: false });
    render(<AnalyzeForm onAnalyze={vi.fn()} loading={false} />);

    fireEvent.change(screen.getByPlaceholderText("Paste PGN here..."), {
      target: { value: "1. e4 e5" },
    });

    await waitFor(() => expect(screen.getByRole("button", { name: "Review Game" })).toBeEnabled());
    expect(screen.getByText(/verified fallback coaching/i)).toBeInTheDocument();
  });
});
