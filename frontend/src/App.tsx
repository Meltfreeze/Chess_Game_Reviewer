import { useEffect, useState } from "react";
import AnalyzeForm from "./components/AnalyzeForm";
import ReviewBoard from "./components/ReviewBoard";
import EvalBar from "./components/EvalBar";
import ReviewSidebar from "./components/ReviewSidebar";
import { analyzeGame } from "./api/client";
import type { AnalysisResult } from "./types";

const STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

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
  const [playerColor, setPlayerColor] = useState<"White" | "Black">("White");
  const [historyIndex, setHistoryIndex] = useState(0);
  const [boardSize, setBoardSize] = useState(computeBoardSize);

  useEffect(() => {
    const onResize = () => setBoardSize(computeBoardSize());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

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
      setPlayerColor(color);
      setHistoryIndex(data.move_data.length);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const currentMove = result && historyIndex > 0 ? result.move_data[historyIndex - 1] : null;
  const fen = currentMove ? currentMove.fen : STARTING_FEN;
  const comment = currentMove ? result!.coach.comments[historyIndex - 1] ?? "" : "";

  return (
    <div className="w-full pt-6 px-6 pb-1">
      <h1 className="text-2xl font-bold mb-4">Chess Game Review</h1>

      <AnalyzeForm onAnalyze={handleAnalyze} loading={loading} progress={progress} />

      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-200 rounded-lg p-3 mb-6">
          {error}
        </div>
      )}

      {result && (
        <div className="flex flex-wrap gap-6 items-start">
          <div className="flex gap-3 shrink-0">
            <EvalBar
              evalCpWhite={currentMove ? currentMove.eval_cp_white : 0}
              evalText={currentMove?.eval}
              height={boardSize}
            />
            <ReviewBoard
              fen={fen}
              boardWidth={boardSize}
              flipped={playerColor === "Black"}
              lastMoveUci={currentMove?.uci ?? null}
              arrowUci={currentMove?.best_uci ?? null}
              badge={currentMove?.classification ?? null}
              interactive={false}
            />
          </div>

          <div className="flex-1 min-w-[360px]">
            <ReviewSidebar
              result={result}
              currentPly={historyIndex}
              currentMove={currentMove}
              comment={comment}
              onSelect={setHistoryIndex}
              height={boardSize}
            />
          </div>
        </div>
      )}
    </div>
  );
}
