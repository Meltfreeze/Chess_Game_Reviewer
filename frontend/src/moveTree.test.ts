import { describe, expect, it } from "vitest";
import {
  ROOT_ID,
  STARTING_FEN,
  addBranch,
  buildTree,
  findChildByUci,
  forwardId,
  goBackward,
  goForward,
  goToEnd,
  goToMainPly,
  goToStart,
  lastMainLineId,
  mainLineAnchorId,
  mainLineIds,
  mainLinePly,
  navigateTo,
  nearestEval,
  pathIds,
  pathUci,
  setNodeError,
  setNodeReview,
} from "./moveTree";
import type { AnalysisResult, MoveData } from "./types";

function move(
  san: string,
  uci: string,
  fen: string,
  turn: "White" | "Black",
  moveNumber: number,
  evalCpWhite: number,
  evaluationText: string
): MoveData {
  return {
    san,
    uci,
    fen,
    turn,
    move_number: moveNumber,
    eval_cp_white: evalCpWhite,
    eval: evaluationText,
  } as MoveData;
}

const result = {
  move_data: [
    move("e4", "e2e4", "after-e4", "White", 1, 20, "+0.2"),
    move("e5", "e7e5", "after-e5", "Black", 1, 5, "+0.1"),
    move("Nf3", "g1f3", "after-nf3", "White", 2, 35, "+0.4"),
  ],
  coach: { summary: "", comments: ["White opens", "Black replies", "Develop"] },
} as AnalysisResult;

describe("moveTree", () => {
  it("builds an ordered main line with review data and coaching comments", () => {
    const tree = buildTree(result);

    expect(tree.rootId).toBe(ROOT_ID);
    expect(tree.currentId).toBe("m3");
    expect(tree.nodes.root.fen).toBe(STARTING_FEN);
    expect(tree.nodes.root.childIds).toEqual(["m1"]);
    expect(tree.nodes.m2.parentId).toBe("m1");
    expect(tree.nodes.m3.comment).toBe("Develop");
    expect(mainLineIds(tree)).toEqual(["root", "m1", "m2", "m3"]);
    expect(pathIds(tree, "m3")).toEqual(["root", "m1", "m2", "m3"]);
    expect(pathUci(tree, "m3")).toEqual(["e2e4", "e7e5", "g1f3"]);
    expect(lastMainLineId(tree)).toBe("m3");
  });

  it("keeps arrow navigation on the main line even after a branch is explored", () => {
    const base = buildTree(result);
    const withBranch = addBranch(base, "m1", "v1", {
      ply: 2,
      san: "c5",
      uci: "c7c5",
      fen: "after-c5",
      moveNumber: 1,
      turn: "Black",
    });

    expect(withBranch.currentId).toBe("v1");
    expect(findChildByUci(withBranch, "m1", "c7c5")).toBe("v1");
    expect(mainLinePly(withBranch, "v1")).toBe(1);
    expect(mainLineAnchorId(withBranch, "v1")).toBe("m1");

    const atMainLineParent = goBackward(withBranch);
    expect(atMainLineParent.currentId).toBe("m1");
    expect(forwardId(atMainLineParent)).toBe("m2");
    expect(goForward(atMainLineParent).currentId).toBe("m2");
  });

  it("replays the most recently navigated variation branch", () => {
    const firstBranch = addBranch(buildTree(result), "m1", "v1", {
      ply: 2,
      san: "c5",
      uci: "c7c5",
      fen: "after-c5",
      moveNumber: 1,
      turn: "Black",
    });
    const nestedBranch = addBranch(firstBranch, "v1", "v2", {
      ply: 3,
      san: "Nf3",
      uci: "g1f3",
      fen: "after-c5-nf3",
      moveNumber: 2,
      turn: "White",
    });

    expect(goBackward(nestedBranch).currentId).toBe("v1");
    expect(forwardId(goBackward(nestedBranch))).toBe("v2");
    expect(goForward(goBackward(nestedBranch)).currentId).toBe("v2");
  });

  it("clamps main-line jumps and preserves the branch selected by navigation", () => {
    const tree = buildTree(result);

    expect(goToMainPly(tree, -10).currentId).toBe(ROOT_ID);
    expect(goToMainPly(tree, 2).currentId).toBe("m2");
    expect(goToMainPly(tree, 99).currentId).toBe("m3");
    expect(goToStart(tree).currentId).toBe(ROOT_ID);
    expect(goToEnd(tree).currentId).toBe("m3");

    const selected = navigateTo(tree, "m2");
    expect(selected.currentId).toBe("m2");
    expect(selected.nodes.root.lastActiveChildId).toBe("m1");
    expect(selected.nodes.m1.lastActiveChildId).toBe("m2");
  });

  it("uses the nearest reviewed ancestor while branch analysis is pending or fails", () => {
    const pending = addBranch(buildTree(result), "m2", "v1", {
      ply: 3,
      san: "Bc4",
      uci: "f1c4",
      fen: "after-bc4",
      moveNumber: 2,
      turn: "White",
    });

    expect(nearestEval(pending, "v1")).toEqual({ cp: 5, text: "+0.1" });

    const reviewedMove = move("Bc4", "f1c4", "after-bc4", "White", 2, 70, "+0.7");
    const reviewed = setNodeReview(pending, "v1", reviewedMove, "A strong developing move.");
    expect(reviewed.nodes.v1.status).toBe("ready");
    expect(reviewed.nodes.v1.comment).toBe("A strong developing move.");
    expect(nearestEval(reviewed, "v1")).toEqual({ cp: 70, text: "+0.7" });

    const failed = setNodeError(reviewed, "v1", "Engine busy");
    expect(failed.nodes.v1.status).toBe("error");
    expect(failed.nodes.v1.error).toBe("Engine busy");
  });
});
