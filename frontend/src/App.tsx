import { useEffect, useState } from "react";
import { Chess } from "chess.js";
import AnalyzeForm from "./components/AnalyzeForm";
import ReviewBoard from "./components/ReviewBoard";
import EvalBar from "./components/EvalBar";
import MoveNav from "./components/MoveNav";
import ReviewSidebar from "./components/ReviewSidebar";
import VariationBanner from "./components/VariationBanner";
import { analyzeGame, reviewMove } from "./api/client";
import type { AnalysisResult } from "./types";
import {
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
  mainLinePly,
  navigateTo,
  nearestEval,
  newBranchId,
  pathUci,
  setNodeError,
  setNodeReview,
  type MoveTree,
} from "./moveTree";

const HEIGHT_RATIO = 0.98;
const EVAL_GROUP = 26 + 12; // eval bar width + gap-3 to the board
const H_CHROME = 28 + 24; // container padding (p-6) + row gap (gap-6)
const PANEL_MIN = 360; // don't shrink the moves/comment column below this

function computeBoardSize(): number {
  if (typeof window === "undefined") return 520;
  const byHeight = Math.floor(window.innerHeight * HEIGHT_RATIO);
  const byWidth = window.innerWidth - H_CHROME - EVAL_GROUP - PANEL_MIN;
  return Math.max(320, Math.min(byHeight, byWidth));
}

export default function App() {
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<{ ply: number; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [tree, setTree] = useState<MoveTree | null>(null);
  const [playerColor, setPlayerColor] = useState<"White" | "Black">("White");
  const [analysisDepth, setAnalysisDepth] = useState(14);
  const [boardSize, setBoardSize] = useState(520);

  useEffect(() => {
    setBoardSize(computeBoardSize());
    const onResize = () => setBoardSize(computeBoardSize());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const hasTree = tree !== null;

  useEffect(() => {
    if (!hasTree) return;
    const steps: Record<string, (t: MoveTree) => MoveTree> = {
      ArrowLeft: goBackward,
      ArrowRight: goForward,
      ArrowUp: goToEnd,
      ArrowDown: goToStart,
    };

    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))) {
        return;
      }
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;

      const step = steps[event.key];
      if (!step) return;
      event.preventDefault();
      setTree((t) => (t ? step(t) : t));
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [hasTree]);

  const handleAnalyze = async (pgn: string, color: "White" | "Black", depth: number) => {
    setLoading(true);
    setError(null);
    setProgress(null);
    try {
      const data = await analyzeGame({
        pgn,
        playerColor: color,
        depth,
        onProgress: (ply, total) => setProgress({ ply, total }),
      });
      setResult(data);
      setTree(buildTree(data));
      setPlayerColor(color);
      setAnalysisDepth(depth);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  /**
   * Any legal move is playable at any position. An existing branch is re-entered
   * rather than duplicated; a new one is created as a variation and sent to
   * /api/move-review so it gets the same coach comment a real move would.
   */
  const handlePieceDrop = (source: string, target: string): boolean => {
    if (!tree) return false;

    const parent = tree.nodes[tree.currentId];
    const candidates = new Chess(parent.fen)
      .moves({ verbose: true })
      .filter((m) => m.from === source && m.to === target);
    if (candidates.length === 0) return false;
    const move = candidates.find((m) => m.promotion === "q") ?? candidates[0];

    const existingId = findChildByUci(tree, parent.id, move.lan);
    if (existingId) {
      setTree((t) => (t ? navigateTo(t, existingId) : t));
      return true;
    }

    const id = newBranchId();
    setTree((t) =>
      t
        ? addBranch(t, parent.id, id, {
            ply: parent.ply + 1,
            san: move.san,
            uci: move.lan,
            fen: move.after,
            moveNumber: Math.floor(parent.ply / 2) + 1,
            turn: parent.ply % 2 === 0 ? "White" : "Black",
          })
        : t
    );

    reviewMove({
      fen: parent.fen,
      uci: move.lan,
      ply: parent.ply,
      history: pathUci(tree, parent.id),
      depth: analysisDepth,
    })
      .then((res) => setTree((t) => (t ? setNodeReview(t, id, res.move, res.comment) : t)))
      .catch((err) =>
        setTree((t) =>
          t ? setNodeError(t, id, err instanceof Error ? err.message : "Move review failed") : t
        )
      );

    return true;
  };

  const node = tree ? tree.nodes[tree.currentId] : null;
  const inVariation = node ? !node.isMainLine : false;
  const evalNow = tree && node ? nearestEval(tree, node.id) : { cp: 0, text: undefined };

  return (
    <div className="w-full pt-6 px-6 pb-1">
      <h1 className="text-2xl font-bold mb-4">Chess Game Review</h1>

      <AnalyzeForm onAnalyze={handleAnalyze} loading={loading} progress={progress} />

      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-200 rounded-lg p-3 mb-6">
          {error}
        </div>
      )}

      {result && tree && node && (
        <div className="flex flex-wrap gap-6 items-start">
          <div className="flex gap-3 shrink-0">
            <EvalBar evalCpWhite={evalNow.cp} evalText={evalNow.text} height={boardSize} />
            <ReviewBoard
              fen={node.fen}
              boardWidth={boardSize}
              flipped={playerColor === "Black"}
              lastMoveUci={node.uci || null}
              arrowUci={node.data?.best_uci ?? null}
              badge={node.data?.classification ?? null}
              interactive
              onPieceDrop={handlePieceDrop}
            />
          </div>

          <div
            className="flex-1 min-w-[360px] flex flex-col gap-3"
            style={{ height: boardSize }}
          >
            {inVariation && (
              <VariationBanner
                onReturn={() =>
                  setTree((t) => (t ? navigateTo(t, mainLineAnchorId(t, t.currentId)) : t))
                }
              />
            )}
            <MoveNav
              canPrev={node.parentId !== null}
              canNext={forwardId(tree) !== null}
              canJumpEnd={tree.currentId !== lastMainLineId(tree)}
              onFirst={() => setTree((t) => (t ? goToStart(t) : t))}
              onPrev={() => setTree((t) => (t ? goBackward(t) : t))}
              onNext={() => setTree((t) => (t ? goForward(t) : t))}
              onLast={() => setTree((t) => (t ? goToEnd(t) : t))}
            />
            <div className="flex-1 min-h-0">
              <ReviewSidebar
                result={result}
                tree={tree}
                currentPly={mainLinePly(tree, tree.currentId)}
                onSelectPly={(ply) => setTree((t) => (t ? goToMainPly(t, ply) : t))}
                onSelectNode={(id) => setTree((t) => (t ? navigateTo(t, id) : t))}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
