import { useEffect, useState } from "react";
import { fetchHealth } from "../api/client";
import type { HealthInfo } from "../types";

interface AnalyzeFormProps {
  onAnalyze: (pgn: string, playerColor: PlayerColor, depth: number) => void;
  loading: boolean;
  progress?: { ply: number; total: number } | null;
}

export default function AnalyzeForm({ onAnalyze, loading, progress }: AnalyzeFormProps) {
  const [pgn, setPgn] = useState("");
  const [playerColor, setPlayerColor] = useState<PlayerColor>("White");
  const [depth, setDepth] = useState(14);
  const [health, setHealth] = useState<HealthInfo | null>(null);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth({ ready: false }));
  }, []);

  const canAnalyze = health?.ready && health?.gemini_configured && !loading && pgn.trim();

  return (
    <div className="bg-panel rounded-xl p-5 mb-6 border border-panelBorder">
      <h2 className="text-xl font-bold mb-4">Analyze a new game</h2>

      <div className="flex flex-wrap items-center gap-4 mb-3 text-sm">
        <ColorToggle value={playerColor} onChange={setPlayerColor} />
        <label className="group ml-auto flex items-center gap-2.5 rounded-lg border border-panelBorder bg-[#21201d] py-1.5 pl-3.5 pr-3 cursor-pointer transition-colors hover:border-[#5c5a57] focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/40">
          <span className="text-[0.9rem] font-semibold uppercase tracking-wider leading-none text-[#8b8987]">
            Depth
          </span>
          <div className="relative flex items-center">
            <select
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
              className="appearance-none bg-transparent pr-5 font-semibold leading-none text-[#e8e8e8] cursor-pointer focus:outline-none"
            >
              <option className="bg-panel text-[#e8e8e8]" value={12}>12</option>
              <option className="bg-panel text-[#e8e8e8]" value={14}>14</option>
              <option className="bg-panel text-[#e8e8e8]" value={16}>16</option>
              <option className="bg-panel text-[#e8e8e8]" value={18}>18</option>
              <option className="bg-panel text-[#e8e8e8]" value={20}>20</option>
            </select>
            <svg
              aria-hidden
              viewBox="0 0 12 12"
              className="pointer-events-none absolute right-0 top-1/2 h-3 w-3 -translate-y-1/2 text-[#8b8987] transition-colors group-hover:text-[#e8e8e8]"
            >
              <path
                d="M2.5 4.5 6 8l3.5-3.5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
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

type PlayerColor = "White" | "Black";

function ColorToggle({
  value,
  onChange,
}: {
  value: PlayerColor;
  onChange: (color: PlayerColor) => void;
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Side you played"
      className="relative flex w-56 p-1 rounded-lg bg-[#21201d] border border-panelBorder"
    >
      <span
        aria-hidden
        className="absolute top-1 bottom-1 left-1 w-[calc(50%-0.25rem)] rounded-md bg-panelBorder transition-transform duration-200 ease-out"
        style={{ transform: value === "Black" ? "translateX(100%)" : "none" }}
      />
      <ColorOption color="White" value={value} onChange={onChange} />
      <ColorOption color="Black" value={value} onChange={onChange} />
    </div>
  );
}

function ColorOption({
  color,
  value,
  onChange,
}: {
  color: PlayerColor;
  value: PlayerColor;
  onChange: (color: PlayerColor) => void;
}) {
  const active = value === color;
  return (
    <label
      className={`relative z-10 flex-1 flex items-center justify-center gap-2 py-1.5 rounded-md font-semibold cursor-pointer transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-accent ${
        active ? "text-white" : "text-[#8b8987] hover:text-[#e8e8e8]"
      }`}
    >
      <input
        type="radio"
        name="player-color"
        className="sr-only"
        checked={active}
        onChange={() => onChange(color)}
      />
      <span
        className={`w-3.5 h-3.5 rounded-full border ${
          color === "White" ? "bg-[#f5f5f0] border-[#d8d7d2]" : "bg-[#1a1917] border-[#5c5a57]"
        }`}
      />
      {color}
    </label>
  );
}
