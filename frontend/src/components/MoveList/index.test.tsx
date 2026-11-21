import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { MoveNode, MoveTree } from "../../moveTree";
import MoveList from "./index";

function node(overrides: Partial<MoveNode> & Pick<MoveNode, "id" | "san">): MoveNode {
  return {
    parentId: null,
    childIds: [],
    lastActiveChildId: null,
    isMainLine: true,
    ply: 0,
    uci: "",
    fen: "",
    moveNumber: 1,
    turn: "White",
    data: null,
    comment: "",
    status: "ready",
    error: null,
    ...overrides,
  };
}

const tree: MoveTree = {
  rootId: "root",
  currentId: "v1",
  nodes: {
    root: node({ id: "root", san: "", childIds: ["m1", "v1"] }),
    m1: node({ id: "m1", san: "e4", parentId: "root", childIds: ["m2"], ply: 1 }),
    m2: node({
      id: "m2",
      san: "e5",
      parentId: "m1",
      ply: 2,
      turn: "Black",
    }),
    v1: node({
      id: "v1",
      san: "d4",
      parentId: "root",
      isMainLine: false,
      ply: 1,
    }),
  },
};

describe("MoveList", () => {
  it("renders main-line and variation moves and selects either", () => {
    const onSelect = vi.fn();
    render(<MoveList tree={tree} onSelect={onSelect} />);

    expect(screen.getByRole("button", { name: /^e4/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^e5/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^d4/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^d4/ }));
    fireEvent.click(screen.getByRole("button", { name: /^e5/ }));
    expect(onSelect.mock.calls).toEqual([["v1"], ["m2"]]);
  });
});
