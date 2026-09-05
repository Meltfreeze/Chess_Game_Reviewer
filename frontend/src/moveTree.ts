import type { AnalysisResult, MoveData } from "./types";

export const STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

export const ROOT_ID = "root";

export type NodeStatus = "ready" | "pending" | "error";

/**
 * One position in the review tree. `data` is the engine's review of the move
 * that led here — null on the root, and null while a variation move is still
 * being reviewed by the backend.
 */
export interface MoveNode {
  id: string;
  parentId: string | null;
  childIds: string[];
  /** Child we last navigated into, so right-arrow can redo variation steps. */
  lastActiveChildId: string | null;
  /** True for positions from the reviewed game itself. */
  isMainLine: boolean;
  /** Plies from the starting position; 0 on the root. */
  ply: number;
  san: string;
  uci: string;
  fen: string;
  moveNumber: number;
  turn: "White" | "Black";
  data: MoveData | null;
  comment: string;
  status: NodeStatus;
  error: string | null;
}

export interface MoveTree {
  nodes: Record<string, MoveNode>;
  rootId: string;
  currentId: string;
}

export type NewNodeFields = Pick<
  MoveNode,
  "ply" | "san" | "uci" | "fen" | "moveNumber" | "turn"
>;

let branchCounter = 0;

export function newBranchId(): string {
  branchCounter += 1;
  return `b${branchCounter}`;
}

export function buildTree(result: AnalysisResult): MoveTree {
  const root: MoveNode = {
    id: ROOT_ID,
    parentId: null,
    childIds: [],
    lastActiveChildId: null,
    isMainLine: true,
    ply: 0,
    san: "",
    uci: "",
    fen: STARTING_FEN,
    moveNumber: 0,
    turn: "White",
    data: null,
    comment: "",
    status: "ready",
    error: null,
  };
  const nodes: Record<string, MoveNode> = { [ROOT_ID]: root };

  let prevId = ROOT_ID;
  result.move_data.forEach((move, i) => {
    const id = `m${i + 1}`;
    nodes[id] = {
      id,
      parentId: prevId,
      childIds: [],
      lastActiveChildId: null,
      isMainLine: true,
      ply: i + 1,
      san: move.san,
      uci: move.uci,
      fen: move.fen,
      moveNumber: move.move_number,
      turn: move.turn,
      data: move,
      comment: result.coach.comments[i] ?? "",
      status: "ready",
      error: null,
    };
    nodes[prevId].childIds.push(id);
    nodes[prevId].lastActiveChildId = id;
    prevId = id;
  });

  return { nodes, rootId: ROOT_ID, currentId: prevId };
}

export function currentNode(tree: MoveTree): MoveNode {
  return tree.nodes[tree.currentId];
}

export function mainLineChild(tree: MoveTree, nodeId: string): string | null {
  const node = tree.nodes[nodeId];
  if (!node) return null;
  for (const id of node.childIds) {
    if (tree.nodes[id]?.isMainLine) return id;
  }
  return null;
}

export function variationChildren(tree: MoveTree, nodeId: string): string[] {
  const node = tree.nodes[nodeId];
  if (!node) return [];
  return node.childIds.filter((id) => !tree.nodes[id]?.isMainLine);
}

/** Root-first ids of the reviewed game, starting with the root itself. */
export function mainLineIds(tree: MoveTree): string[] {
  const ids: string[] = [];
  let id: string | null = tree.rootId;
  while (id) {
    ids.push(id);
    id = mainLineChild(tree, id);
  }
  return ids;
}

export function pathIds(tree: MoveTree, nodeId: string): string[] {
  const path: string[] = [];
  let id: string | null = nodeId;
  while (id && tree.nodes[id]) {
    path.unshift(id);
    id = tree.nodes[id].parentId;
  }
  return path;
}

/** UCI moves from the starting position up to and including `nodeId`. */
export function pathUci(tree: MoveTree, nodeId: string): string[] {
  return pathIds(tree, nodeId)
    .map((id) => tree.nodes[id].uci)
    .filter((uci) => uci !== "");
}

export function isAncestorOf(tree: MoveTree, ancestorId: string, nodeId: string): boolean {
  let id: string | null = nodeId;
  while (id && tree.nodes[id]) {
    if (id === ancestorId) return true;
    id = tree.nodes[id].parentId;
  }
  return false;
}

/** Ply of the nearest main-line ancestor — where the eval graph cursor sits. */
export function mainLinePly(tree: MoveTree, nodeId: string): number {
  let id: string | null = nodeId;
  while (id && tree.nodes[id]) {
    const node: MoveNode = tree.nodes[id];
    if (node.isMainLine) return node.ply;
    id = node.parentId;
  }
  return 0;
}

/** Nearest known eval, so pending variation nodes don't flash the bar to 0.0. */
export function nearestEval(tree: MoveTree, nodeId: string): { cp: number; text?: string } {
  let id: string | null = nodeId;
  while (id && tree.nodes[id]) {
    const node: MoveNode = tree.nodes[id];
    if (node.data) return { cp: node.data.eval_cp_white, text: node.data.eval };
    id = node.parentId;
  }
  return { cp: 0 };
}

export function findChildByUci(tree: MoveTree, nodeId: string, uci: string): string | null {
  const node = tree.nodes[nodeId];
  if (!node) return null;
  return node.childIds.find((id) => tree.nodes[id]?.uci === uci) ?? null;
}

/**
 * Point `currentId` at `nodeId` and mark every edge on the way as last-active,
 * so that stepping back and forward inside a variation retraces it.
 */
export function navigateTo(tree: MoveTree, nodeId: string): MoveTree {
  if (!tree.nodes[nodeId]) return tree;
  const path = pathIds(tree, nodeId);
  const nodes = { ...tree.nodes };
  for (let i = 0; i < path.length - 1; i += 1) {
    const parent = nodes[path[i]];
    if (parent.lastActiveChildId !== path[i + 1]) {
      nodes[path[i]] = { ...parent, lastActiveChildId: path[i + 1] };
    }
  }
  return { ...tree, nodes, currentId: nodeId };
}

export function goBackward(tree: MoveTree): MoveTree {
  const parentId = currentNode(tree).parentId;
  return parentId ? { ...tree, currentId: parentId } : tree;
}

/**
 * The reviewed game always advances along itself — arrows never wander into a
 * variation. Inside a variation, replay the branch we last walked into.
 */
export function forwardId(tree: MoveTree): string | null {
  const node = currentNode(tree);
  const nextId = node.isMainLine ? mainLineChild(tree, node.id) : node.lastActiveChildId;
  return nextId && tree.nodes[nextId] ? nextId : null;
}

export function goForward(tree: MoveTree): MoveTree {
  const nextId = forwardId(tree);
  return nextId ? navigateTo(tree, nextId) : tree;
}

export function goToStart(tree: MoveTree): MoveTree {
  return { ...tree, currentId: tree.rootId };
}

export function lastMainLineId(tree: MoveTree): string {
  const ids = mainLineIds(tree);
  return ids[ids.length - 1];
}

export function goToEnd(tree: MoveTree): MoveTree {
  return navigateTo(tree, lastMainLineId(tree));
}

export function goToMainPly(tree: MoveTree, ply: number): MoveTree {
  const ids = mainLineIds(tree);
  const id = ids[Math.max(0, Math.min(ids.length - 1, ply))];
  return id ? navigateTo(tree, id) : tree;
}

/** Nearest main-line ancestor — the "back to the game" target from a variation. */
export function mainLineAnchorId(tree: MoveTree, nodeId: string): string {
  let id: string | null = nodeId;
  while (id && tree.nodes[id]) {
    if (tree.nodes[id].isMainLine) return id;
    id = tree.nodes[id].parentId;
  }
  return tree.rootId;
}

/** Add a variation child under `parentId` and navigate into it. */
export function addBranch(
  tree: MoveTree,
  parentId: string,
  id: string,
  fields: NewNodeFields
): MoveTree {
  const parent = tree.nodes[parentId];
  if (!parent) return tree;

  const node: MoveNode = {
    ...fields,
    id,
    parentId,
    childIds: [],
    lastActiveChildId: null,
    isMainLine: false,
    data: null,
    comment: "",
    status: "pending",
    error: null,
  };

  return {
    ...tree,
    currentId: id,
    nodes: {
      ...tree.nodes,
      [id]: node,
      [parentId]: {
        ...parent,
        childIds: [...parent.childIds, id],
        lastActiveChildId: id,
      },
    },
  };
}

export function setNodeReview(
  tree: MoveTree,
  nodeId: string,
  data: MoveData,
  comment: string
): MoveTree {
  const node = tree.nodes[nodeId];
  if (!node) return tree;
  return {
    ...tree,
    nodes: {
      ...tree.nodes,
      [nodeId]: { ...node, data, comment, status: "ready", error: null },
    },
  };
}

export function setNodeError(tree: MoveTree, nodeId: string, message: string): MoveTree {
  const node = tree.nodes[nodeId];
  if (!node) return tree;
  return {
    ...tree,
    nodes: { ...tree.nodes, [nodeId]: { ...node, status: "error", error: message } },
  };
}
