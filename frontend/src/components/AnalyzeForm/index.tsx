import { useEffect, useState, type DragEvent } from "react";
import { fetchHealth } from "../../api/client";
import { lookupOpening } from "../../openingLookup";
import { parsePgnPreview, type PgnParseState } from "../../pgnPreview";
import type { AnalysisCompletion, AnalysisFailure, HealthInfo } from "../../types";
import GameStatusSlot, { type GameStatusState } from "../GameStatusSlot";
import {
  DepthBand,
  DepthBands,
  DepthCard,
  DepthHeading,
  DepthHint,
  DepthLabel,
  DepthOutput,
  DepthSlider,
  DropZone,
  EngineWarning,
  FormColumn,
  FormContainer,
  GeminiWarning,
  HiddenFileInput,
  Layout,
  PgnInput,
  Placeholder,
  PlaySvg,
  SpinnerMark,
  SubmitButton,
  TextareaBox,
  Title,
  UploadLabel,
  UploadRow,
  UploadSvg,
} from "./styledcomponents";

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
    <FormContainer>
      <Title>Analyze a new game</Title>

      <Layout>
        <DropZone
          data-testid="pgn-drop-zone"
          onDragEnter={() => !loading && setIsDragging(true)}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          $dragging={isDragging}
        >
          <TextareaBox>
            {!pgn && (
              <Placeholder aria-hidden="true">
                {PGN_PREVIEW}
              </Placeholder>
            )}
            <PgnInput
              aria-label="PGN"
              value={pgn}
              readOnly={loading}
              aria-disabled={loading}
              onChange={(event) => setPgn(event.target.value)}
            />
          </TextareaBox>

          <UploadRow>
            <UploadLabel $loading={loading}>
              <HiddenFileInput
                type="file"
                accept=".pgn,.txt"
                disabled={loading}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  file.text().then(setPgn);
                }}
              />
              <UploadIcon />
              Upload PGN file
            </UploadLabel>
          </UploadRow>
        </DropZone>

        <FormColumn>
          <DepthCard>
            <DepthHeading>
              <DepthLabel htmlFor="analysis-depth">
                Analysis depth
              </DepthLabel>
              <DepthOutput htmlFor="analysis-depth">
                {depth}
              </DepthOutput>
            </DepthHeading>
            <DepthHint>Higher goes deeper, but takes longer to run.</DepthHint>
            <DepthSlider
              id="analysis-depth"
              aria-label="Analysis depth"
              type="range"
              min={MIN_DEPTH}
              max={MAX_DEPTH}
              step={1}
              value={depth}
              disabled={loading}
              onChange={(event) => setDepth(Number(event.target.value))}
              $progress={depthProgress}
            />
            <DepthBands>
              {(["Quick", "Balanced", "Deep"] as const).map((label) => (
                <DepthBand
                  key={label}
                  $active={depthBand === label}
                >
                  {label}
                </DepthBand>
              ))}
            </DepthBands>
          </DepthCard>

          <GameStatusSlot state={statusState} />

          <div>
            <div title={invalidForSubmit ? "Paste a valid PGN first" : undefined}>
              <SubmitButton
                type="button"
                disabled={!canAnalyze}
                onClick={handleAnalyze}
              >
                {loading ? <Spinner /> : <PlayIcon />}
                {loading ? "Reviewing…" : "Review Game"}
              </SubmitButton>
            </div>
          </div>
        </FormColumn>
      </Layout>

      {health && !health.ready && (
        <EngineWarning>Stockfish not ready: {health.error || "binary missing"}</EngineWarning>
      )}
      {health && !health.gemini_configured && (
        <GeminiWarning>
          Gemini is not configured; verified fallback coaching will be used.
        </GeminiWarning>
      )}
    </FormContainer>
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
    <UploadSvg aria-hidden="true" viewBox="0 0 24 24" strokeWidth="2">
      <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5 14v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4" strokeLinecap="round" />
    </UploadSvg>
  );
}

function PlayIcon() {
  return (
    <PlaySvg aria-hidden="true" viewBox="0 0 20 20">
      <path d="M5.75 3.9a1 1 0 0 1 1.53-.85l9 6.1a1 1 0 0 1 0 1.7l-9 6.1a1 1 0 0 1-1.53-.85V3.9Z" />
    </PlaySvg>
  );
}

function Spinner() {
  return <SpinnerMark aria-hidden="true" />;
}
