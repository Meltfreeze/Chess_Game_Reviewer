import { useEffect, useRef, useState } from "react";
import { fetchHealth } from "../api/client";
import type { HealthInfo } from "../types";

const DEPTH_OPTIONS = [12, 14, 16, 18, 20] as const;

interface AnalyzeFormProps {
  onAnalyze: (pgn: string, playerColor: PlayerColor, depth: number) => void;
  loading: boolean;
  progress?: { ply: number; total: number } | null;
}

export default function AnalyzeForm({ onAnalyze, loading, progress }: AnalyzeFormProps) {
  const [pgn, setPgn] = useState("");
  const [playerColor, setPlayerColor] = useState<PlayerColor>("White");
  const [depth, setDepth] = useState(14);
  const [depthListOpen, setDepthListOpen] = useState(false);
  const [highlightedDepthIndex, setHighlightedDepthIndex] = useState(0);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const depthControlRef = useRef<HTMLDivElement>(null);
  const depthButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth({ ready: false }));
  }, []);

  useEffect(() => {
    if (!depthListOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (!depthControlRef.current?.contains(event.target as Node)) {
        setDepthListOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setDepthListOpen(false);
        depthButtonRef.current?.focus();
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [depthListOpen]);

  const openDepthList = () => {
    const selectedIndex = DEPTH_OPTIONS.findIndex((option) => option === depth);
    setHighlightedDepthIndex(selectedIndex >= 0 ? selectedIndex : 0);
    setDepthListOpen(true);
  };

  const selectDepth = (nextDepth: number) => {
    setDepth(nextDepth);
    setDepthListOpen(false);
    depthButtonRef.current?.focus();
  };

  const handleDepthKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "Escape") return;

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (depthListOpen) {
        selectDepth(DEPTH_OPTIONS[highlightedDepthIndex]);
      } else {
        openDepthList();
      }
      return;
    }

    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;

    event.preventDefault();
    if (!depthListOpen) {
      openDepthList();
      return;
    }

    const direction = event.key === "ArrowDown" ? 1 : -1;
    setHighlightedDepthIndex((current) =>
      (current + direction + DEPTH_OPTIONS.length) % DEPTH_OPTIONS.length
    );
  };

  const canAnalyze = health?.ready && health?.gemini_configured && !loading && pgn.trim();

  return (
    <div className="bg-panel rounded-xl p-5 mb-6 border border-panelBorder">
      <h2 className="text-xl font-bold mb-4">Analyze a new game</h2>

      <div className="flex flex-wrap items-center gap-4 mb-3 text-sm">
        <ColorToggle value={playerColor} onChange={setPlayerColor} />
        <div
          ref={depthControlRef}
          className="relative ml-auto flex items-center gap-2.5 rounded-lg border border-panelBorder bg-[#21201d] py-1.5 pl-1.5 pr-1.5 transition-colors focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/40"
        >
          <span className="text-[0.9rem] leading-none text-[#8b8987]">
            Depth
          </span>
          <button
            ref={depthButtonRef}
            type="button"
            aria-label={`Select analysis depth, current ${depth}`}
            aria-haspopup="listbox"
            aria-expanded={depthListOpen}
            aria-controls="depth-options"
            onClick={() => (depthListOpen ? setDepthListOpen(false) : openDepthList())}
            onKeyDown={handleDepthKeyDown}
            className="min-w-12 rounded-md bg-panelBorder px-3 py-1.5 font-semibold leading-none text-[#e8e8e8] transition-colors hover:bg-[#5c5a57] focus:outline-none"
          >
            {depth}
          </button>

          {depthListOpen && (
            <div
              id="depth-options"
              role="listbox"
              aria-label="Analysis depth"
              className="absolute right-0 top-full z-20 mt-1.5 min-w-24 overflow-hidden rounded-lg border border-panelBorder bg-panel p-1 shadow-xl"
            >
              {DEPTH_OPTIONS.map((option, index) => {
                const active = option === depth;
                const highlighted = index === highlightedDepthIndex;
                return (
                  <button
                    key={option}
                    type="button"
                    role="option"
                    aria-selected={active}
                    onMouseEnter={() => setHighlightedDepthIndex(index)}
                    onClick={() => selectDepth(option)}
                    className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-left font-semibold transition-colors focus:outline-none ${
                      active
                        ? "bg-accent/20 text-accent"
                        : highlighted
                          ? "bg-panelBorder text-[#e8e8e8]"
                          : "text-[#8b8987] hover:bg-panelBorder hover:text-[#e8e8e8]"
                    }`}
                  >
                    <span>{option}</span>
                    {active && <span aria-hidden>✓</span>}
                  </button>
                );
              })}
            </div>
          )}
        </div>
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
