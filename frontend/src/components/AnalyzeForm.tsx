import { useEffect, useState } from "react";
import { fetchHealth } from "../api/client";
import type { HealthInfo } from "../types";

interface AnalyzeFormProps {
  onAnalyze: (pgn: string, playerColor: "White" | "Black", depth: number) => void;
  loading: boolean;
  progress?: { ply: number; total: number } | null;
}

export default function AnalyzeForm({ onAnalyze, loading, progress }: AnalyzeFormProps) {
  const [pgn, setPgn] = useState("");
  const [playerColor, setPlayerColor] = useState<"White" | "Black">("White");
  const [depth, setDepth] = useState(18);
  const [health, setHealth] = useState<HealthInfo | null>(null);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth({ ready: false }));
  }, []);

  const canAnalyze = health?.ready && health?.gemini_configured && !loading && pgn.trim();

  return (
    <div className="bg-panel rounded-xl p-5 mb-6 border border-panelBorder">
      <h2 className="text-xl font-bold mb-4">Analyze a new game</h2>

      <div className="flex flex-wrap gap-4 mb-3 text-sm">
        <label className="flex items-center gap-2">
          <input
            type="radio"
            checked={playerColor === "White"}
            onChange={() => setPlayerColor("White")}
          />
          White
        </label>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            checked={playerColor === "Black"}
            onChange={() => setPlayerColor("Black")}
          />
          Black
        </label>
        <label className="flex items-center gap-2 ml-auto">
          Depth
          <select
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
            className="bg-panelBorder rounded px-2 py-1"
          >
            <option value={16}>16</option>
            <option value={18}>18</option>
            <option value={20}>20</option>
          </select>
        </label>
      </div>

      <textarea
        value={pgn}
        onChange={(e) => setPgn(e.target.value)}
        placeholder="Paste PGN here..."
        className="w-full h-36 bg-[#21201d] border border-panelBorder rounded-lg p-3 text-sm resize-y"
      />

      <div className="mt-2 flex flex-wrap items-center gap-3">
        <label className="text-sm text-gray-400 cursor-pointer hover:text-gray-200">
          <input
            type="file"
            accept=".pgn,.txt"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              file.text().then(setPgn);
            }}
          />
          Upload PGN file
        </label>
      </div>

      {health && !health.ready && (
        <p className="text-red-400 text-sm mt-2">Stockfish not ready: {health.error || "binary missing"}</p>
      )}
      {health && !health.gemini_configured && (
        <p className="text-amber-400 text-sm mt-2">Set GEMINI_API_KEY in .env for AI coaching.</p>
      )}

      <button
        type="button"
        disabled={!canAnalyze}
        onClick={() => onAnalyze(pgn, playerColor, depth)}
        className="mt-4 px-6 py-2.5 rounded-lg font-bold bg-green-700 hover:bg-green-600 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {loading
          ? progress
            ? `Analyzing move ${progress.ply}/${progress.total}…`
            : "Analyzing…"
          : "Review Game"}
      </button>
    </div>
  );
}
