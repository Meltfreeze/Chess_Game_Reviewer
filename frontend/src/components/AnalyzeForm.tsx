import { useEffect, useState, type DragEvent } from "react";
import { fetchHealth } from "../api/client";
import { lookupOpening } from "../openingLookup";
import { parsePgnPreview, type PgnParseState } from "../pgnPreview";
import type { AnalysisCompletion, AnalysisFailure, HealthInfo } from "../types";
import GameStatusSlot, { type GameStatusState } from "./GameStatusSlot";

const MIN_DEPTH = 8;
const MAX_DEPTH = 22;

const PGN_PREVIEW = `1. e4 e5 2. Nf3 Nc6 3. Bb5 a6
4. Ba4 Nf6 5. O-O Be7 6. Re1 b5
7. Bb3 d6 8. c3 O-O 9. h3 Nb8`;

interface AnalyzeFormProps {
  onAnalyze: (pgn: string, depth: number) => void;
  loading: boolean;
  progress?: { ply: number; total: number } | null;
  analysisFailure?: AnalysisFailure | null;
  analysisCompletion?: AnalysisCompletion | null;
}

export default function AnalyzeForm({
  onAnalyze,
  loading,
  progress,
  analysisFailure = null,
  analysisCompletion = null,
}: AnalyzeFormProps) {
  const [pgn, setPgn] = useState("");
  const [depth, setDepth] = useState(16);
  const [isDragging, setIsDragging] = useState(false);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [parseState, setParseState] = useState<PgnParseState>({ kind: "empty" });

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth({ ready: false }));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      const parsed = parsePgnPreview(pgn);
      if (cancelled) return;
      setParseState(parsed);

      if (parsed.kind === "valid" && (!parsed.preview.opening || !parsed.preview.eco)) {
        try {
          const opening = await lookupOpening(parsed.preview.uciMoves);
          if (!cancelled && opening) {
            setParseState((current) =>
              current.kind === "valid" && current.preview.sourcePgn === parsed.preview.sourcePgn
                ? {
                    kind: "valid",
                    preview: {
                      ...current.preview,
                      opening: current.preview.opening ?? opening.name,
                      eco: current.preview.eco ?? opening.eco,
                    },
                  }
                : current
            );
          }
        } catch {
          // Opening recognition is optional; PGN validity does not depend on it.
        }
      }
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [pgn]);

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (loading) return;
    event.dataTransfer.dropEffect = "copy";
    setIsDragging(true);
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    if (event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget)) {
      return;
    }
    setIsDragging(false);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    if (loading) return;
    const file = event.dataTransfer.files?.[0];
    if (!file) return;
    file.text().then(setPgn);
  };

  const depthBand = depth <= 12 ? "Quick" : depth >= 18 ? "Deep" : "Balanced";
  const depthProgress = ((depth - MIN_DEPTH) / (MAX_DEPTH - MIN_DEPTH)) * 100;
  const validPreview = parseState.kind === "valid" && parseState.preview.sourcePgn === pgn.trim()
    ? parseState.preview
    : null;
  const failed = validPreview && analysisFailure?.pgn === validPreview.sourcePgn
    ? analysisFailure
    : null;
  const completed = validPreview && analysisCompletion?.pgn === validPreview.sourcePgn
    ? analysisCompletion
    : null;
  const statusState: GameStatusState = validPreview
    ? loading
      ? { kind: "running", preview: validPreview, progress }
      : failed
        ? { kind: "failed", preview: validPreview, reason: failureMessage(failed) }
        : completed
          ? {
              kind: "completed",
              preview: validPreview,
              commentarySucceeded: completed.commentarySucceeded,
              commentaryStatus: completed.commentaryStatus,
            }
          : { kind: "valid", preview: validPreview }
    : parseState;
  const canAnalyze = Boolean(health?.ready && !loading && validPreview);
  const invalidForSubmit = parseState.kind !== "valid";

  const handleAnalyze = () => {
    if (loading) return;
    const current = parsePgnPreview(pgn);
    if (current.kind !== "valid") {
      setParseState(current);
      return;
    }
    onAnalyze(current.preview.sourcePgn, depth);
  };

  return (
    <div className="mb-6 rounded-2xl border border-panelBorder bg-panel p-5 min-[760px]:p-7">
      <h2 className="mb-5 text-xl font-bold text-[#f2f1ed]">Analyze a new game</h2>

      <div className="grid gap-6 min-[760px]:grid-cols-[minmax(0,1.55fr)_minmax(280px,1fr)]">
        <div
          data-testid="pgn-drop-zone"
          onDragEnter={() => !loading && setIsDragging(true)}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`overflow-hidden rounded-xl border border-dashed bg-[#21201d] transition-colors ${
            isDragging
              ? "border-accent bg-accent/5 ring-2 ring-accent/30"
              : "border-[#4a4742]"
          }`}
        >
          <div className="relative min-h-64 min-[760px]:min-h-72">
            {!pgn && (
              <pre
                aria-hidden="true"
                className="pointer-events-none absolute inset-0 whitespace-pre-wrap p-6 font-mono text-sm leading-8 text-[#756d61]"
              >
                {PGN_PREVIEW}
              </pre>
            )}
            <textarea
              aria-label="PGN"
              value={pgn}
              readOnly={loading}
              aria-disabled={loading}
              onChange={(event) => setPgn(event.target.value)}
              className="absolute inset-0 z-10 h-full w-full resize-none bg-transparent p-6 font-mono text-sm leading-8 text-[#e8e6df] caret-accent outline-none focus:ring-2 focus:ring-inset focus:ring-accent/50 read-only:cursor-not-allowed read-only:opacity-75"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t border-panelBorder px-4 py-3">
            <label className={`inline-flex items-center gap-2 rounded-lg border border-[#4a4742] px-3 py-2 text-sm font-medium text-[#bdb7ae] transition-colors focus-within:ring-2 focus-within:ring-accent/50 ${loading ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:border-accent/70 hover:text-[#eeeae3]"}`}>
              <input
                type="file"
                accept=".pgn,.txt"
                className="sr-only"
                disabled={loading}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  file.text().then(setPgn);
                }}
              />
              <UploadIcon />
              Upload PGN file
            </label>
          </div>
        </div>

        <div className="flex min-w-0 flex-col gap-5">
          <div className="rounded-xl border border-panelBorder bg-[#292724] p-5">
            <div className="flex items-center justify-between gap-4">
              <label htmlFor="analysis-depth" className="text-sm font-semibold text-[#bdb7ae]">
                Analysis depth
              </label>
              <output htmlFor="analysis-depth" className="text-xl font-semibold text-accent">
                {depth}
              </output>
            </div>
            <p className="mt-1 text-sm text-[#756f67]">Higher goes deeper, but takes longer to run.</p>
            <input
              id="analysis-depth"
              aria-label="Analysis depth"
              type="range"
              min={MIN_DEPTH}
              max={MAX_DEPTH}
              step={1}
              value={depth}
              disabled={loading}
              onChange={(event) => setDepth(Number(event.target.value))}
              style={{
                background: `linear-gradient(to right, #e58f2a 0%, #e58f2a ${depthProgress}%, #56514b ${depthProgress}%, #56514b 100%)`,
              }}
              className="mt-7 h-1.5 w-full cursor-pointer appearance-none rounded-full outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-4 focus-visible:ring-offset-[#292724] [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-[#292724] [&::-moz-range-thumb]:bg-accent [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-[#292724] [&::-webkit-slider-thumb]:bg-accent [&::-webkit-slider-thumb]:shadow-[0_0_0_2px_#e58f2a]"
            />
            <div className="mt-4 flex justify-between text-xs font-medium">
              {(["Quick", "Balanced", "Deep"] as const).map((label) => (
                <span
                  key={label}
                  className={depthBand === label ? "font-semibold text-accent" : "text-[#756f67]"}
                >
                  {label}
                </span>
              ))}
            </div>
          </div>

          <GameStatusSlot state={statusState} />

          <div>
            <div title={invalidForSubmit ? "Paste a valid PGN first" : undefined}>
              <button
                type="button"
                disabled={!canAnalyze}
                onClick={handleAnalyze}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-6 py-3.5 font-bold text-[#1c1400] transition-colors hover:bg-[#f0a444] focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-panel disabled:cursor-not-allowed disabled:bg-[#272522] disabled:text-[#756f67] disabled:hover:bg-[#272522]"
              >
                {loading ? <Spinner /> : <PlayIcon />}
                {loading ? "Reviewing…" : "Review Game"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {health && !health.ready && (
        <p className="text-red-400 text-sm mt-2">Stockfish not ready: {health.error || "binary missing"}</p>
      )}
      {health && !health.gemini_configured && (
        <p className="text-amber-400 text-sm mt-2">
          Gemini is not configured; verified fallback coaching will be used.
        </p>
      )}
    </div>
  );
}

function failureMessage(failure: AnalysisFailure) {
  if (failure.kind === "timeout") {
    return `The analysis timed out at depth ${failure.depth}. Try a lower depth.`;
  }
  if (failure.kind === "engine") return "The engine stopped unexpectedly. Try again.";
  return "Something went wrong during the review. Try again.";
}

function UploadIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current" strokeWidth="2">
      <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5 14v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" strokeLinecap="round" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4 fill-current">
      <path d="M5.75 3.9a1 1 0 0 1 1.53-.85l9 6.1a1 1 0 0 1 0 1.7l-9 6.1a1 1 0 0 1-1.53-.85V3.9Z" />
    </svg>
  );
}

function Spinner() {
  return <span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />;
}
