import { useState } from "react";
import AnalyzeForm from "./components/AnalyzeForm";
import ReviewBoard from "./components/ReviewBoard";
import MoveList from "./components/MoveList";
import EvalBar from "./components/EvalBar";
import EvalGraph from "./components/EvalGraph";
import CoachPanel from "./components/CoachPanel";
import { analyzeGame } from "./api/client";
import type { AnalysisResult } from "./types";

const STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

export default function App() {
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<{ ply: number; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [playerColor, setPlayerColor] = useState<"White" | "Black">("White");
  const [historyIndex, setHistoryIndex] = useState(0);

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
    <div className="max-w-6xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-4">Chess Game Review</h1>

      <AnalyzeForm onAnalyze={handleAnalyze} loading={loading} progress={progress} />

      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-200 rounded-lg p-3 mb-6">
          {error}
        </div>
      )}

      {result && (
        <div className="flex flex-wrap gap-6">
          <div className="flex gap-3">
            <EvalBar evalCpWhite={currentMove ? currentMove.eval_cp_white : 0} />
            <ReviewBoard
              fen={fen}
              flipped={playerColor === "Black"}
              lastMoveUci={currentMove?.uci ?? null}
              arrowUci={currentMove?.best_uci ?? null}
              badge={currentMove?.classification ?? null}
              interactive={false}
            />
          </div>

          <div className="flex-1 min-w-[280px] flex flex-col gap-4">
            <EvalGraph history={result.hist} currentPly={historyIndex} onSelect={setHistoryIndex} />
            <MoveList moves={result.move_data} currentPly={historyIndex} onSelect={setHistoryIndex} />
            <CoachPanel
              summary={result.coach.summary}
              comment={comment}
              classification={currentMove?.classification ?? null}
              bestLine={currentMove?.best_line}
            />
          </div>
        </div>
      )}
    </div>
  );
}
