import { useMemo } from "react";
import { Chessboard } from "react-chessboard";
import type { CustomPieces, CustomSquareStyles, Piece, Square } from "react-chessboard/dist/chessboard/types";
import type { GamePreview, PgnParseState } from "../../pgnPreview";
import type { CommentaryStatus } from "../../types";
import {
  AlertSvg,
  BookSvg,
  CalendarSvg,
  CheckSvg,
  CompletionStatus,
  Eco,
  Elo,
  EmptyBox,
  EmptyIconShell,
  InvalidBox,
  InvalidIconShell,
  MetaRow,
  MiniBoardFrame,
  MiniPieceImage,
  OpeningName,
  OpeningRow,
  PawnSvg,
  PlayerMarker,
  PlayerName,
  Players,
  PlayerText,
  Preview,
  PreviewCopy,
  PreviewHeader,
  PreviewLabel,
  ProgressFill,
  ProgressTrack,
  Result,
  Slot,
  SpinnerMark,
  StateCopy,
  StateDescription,
  StateTitle,
  StatusPillElement,
  TruncatedMeta,
  Versus,
} from "./styledcomponents";

export type GameStatusState =
  | PgnParseState
  | { kind: "running"; preview: GamePreview; progress?: { ply: number; total: number } | null }
  | { kind: "failed"; preview: GamePreview; reason: string }
  | {
      kind: "completed";
      preview: GamePreview;
      commentarySucceeded: boolean;
      commentaryStatus?: CommentaryStatus;
    };

interface GameStatusSlotProps {
  state: GameStatusState;
}

const PIECE_NAMES: Record<string, string> = {
  P: "Pawn",
  N: "Knight",
  B: "Bishop",
  R: "Rook",
  Q: "Queen",
  K: "King",
};

const MINI_PIECES = Object.fromEntries(
  (["w", "b"] as const).flatMap((color) =>
    Object.entries(PIECE_NAMES).map(([code, name]) => {
      const pieceKey = `${color}${code}` as Piece;
      return [
        pieceKey,
        ({ squareWidth }: { squareWidth: number }) => (
          <MiniPieceImage
            src={`/pieces/${color === "w" ? "White" : "Black"}-${name}.png`}
            alt=""
            draggable={false}
            $size={squareWidth}
          />
        ),
      ];
    })
  )
) as CustomPieces;

export default function GameStatusSlot({ state }: GameStatusSlotProps) {
  return (
    <Slot aria-live="polite" aria-atomic="true">
      {state.kind === "empty" && <EmptyState />}
      {state.kind === "invalid" && <InvalidState reason={state.reason} />}
      {(state.kind === "valid" || state.kind === "running" || state.kind === "failed" || state.kind === "completed") && (
        <PreviewCard state={state} />
      )}
    </Slot>
  );
}

function EmptyState() {
  return (
    <EmptyBox>
      <EmptyIconShell>
        <PawnIcon />
      </EmptyIconShell>
      <StateCopy>
        <StateTitle>Paste a PGN to preview the game</StateTitle>
        <StateDescription>Players, result, and opening show up here.</StateDescription>
      </StateCopy>
    </EmptyBox>
  );
}

function InvalidState({ reason }: { reason: string }) {
  return (
    <InvalidBox>
      <InvalidIconShell>
        <AlertIcon />
      </InvalidIconShell>
      <StateCopy $constrained>
        <StateTitle>Couldn&apos;t read this game</StateTitle>
        <StateDescription $invalid>{reason}</StateDescription>
      </StateCopy>
    </InvalidBox>
  );
}

function PreviewCard({
  state,
}: {
  state: Extract<GameStatusState, { kind: "valid" | "running" | "failed" | "completed" }>;
}) {
  const { preview } = state;
  const meta = [
    preview.date,
    `${preview.moveCount} ${preview.moveCount === 1 ? "move" : "moves"}`,
    preview.event,
    preview.termination,
  ].filter(Boolean);
  const progressPercent = state.kind === "running" && state.progress?.total
    ? Math.min(100, Math.max(0, (state.progress.ply / state.progress.total) * 100))
    : null;
  const geminiSucceeded = state.kind === "completed"
    ? geminiRespondedSuccessfully(state.commentarySucceeded, state.commentaryStatus)
    : false;

  return (
    <Preview $failed={state.kind === "failed"}>
      <MiniBoard preview={preview} />

      <PreviewCopy>
        <PreviewHeader>
          <PreviewLabel>
            Game preview
          </PreviewLabel>
          <StatusPill kind={state.kind} />
        </PreviewHeader>

        <Players>
          <Player color="white" name={preview.white} elo={preview.whiteElo} />
          <Versus>vs</Versus>
          <Player color="black" name={preview.black} elo={preview.blackElo} />
          <Result>
            {preview.resultLabel}
          </Result>
        </Players>

        <OpeningRow>
          <BookIcon />
          <OpeningName $recognized={Boolean(preview.opening)} title={preview.opening}>
            {preview.opening ?? "Opening not recognized"}
          </OpeningName>
          {preview.eco && (
            <Eco>
              {preview.eco}
            </Eco>
          )}
        </OpeningRow>

        <MetaRow>
          <CalendarIcon />
          {state.kind === "running" ? (
            <span>
              {state.progress?.total
                ? `Analyzing move ${state.progress.ply} of ${state.progress.total}`
                : "Analyzing…"}
            </span>
          ) : state.kind === "failed" ? (
            <TruncatedMeta $tone="error" title={state.reason}>{state.reason}</TruncatedMeta>
          ) : state.kind === "completed" ? (
            <CompletionStatus $succeeded={geminiSucceeded}>
              {geminiSucceeded ? "Status: Success" : "Status: Failure"}
            </CompletionStatus>
          ) : (
            <TruncatedMeta title={meta.join(" · ")}>{meta.join(" · ")}</TruncatedMeta>
          )}
        </MetaRow>
      </PreviewCopy>

      {state.kind === "running" && (
        <ProgressTrack>
          <ProgressFill $percent={progressPercent} />
        </ProgressTrack>
      )}
    </Preview>
  );
}

function geminiRespondedSuccessfully(succeeded: boolean, status?: CommentaryStatus) {
  if (!status) return succeeded;
  return status.gemini_attempted && status.generation_complete;
}

function Player({ color, name, elo }: { color: "white" | "black"; name: string; elo?: string }) {
  const title = elo ? `${name} (${elo})` : name;
  return (
    <PlayerName title={title}>
      <PlayerMarker
        aria-hidden="true"
        $color={color}
      />
      <PlayerText>{name}</PlayerText>
      {elo && <Elo>{elo}</Elo>}
    </PlayerName>
  );
}

function StatusPill({ kind }: { kind: "valid" | "running" | "failed" | "completed" }) {
  if (kind === "running") {
    return (
      <StatusPillElement $kind="running">
        <Spinner /> Analyzing
      </StatusPillElement>
    );
  }
  if (kind === "failed") {
    return (
      <StatusPillElement $kind="failed">
        <AlertIcon small /> Review failed
      </StatusPillElement>
    );
  }
  if (kind === "completed") {
    return (
      <StatusPillElement $kind="completed">
        <CheckIcon /> Review complete
      </StatusPillElement>
    );
  }
  return (
    <StatusPillElement $kind="valid">
      <CheckIcon /> PGN valid
    </StatusPillElement>
  );
}

function MiniBoard({ preview }: { preview: GamePreview }) {
  const squareStyles = useMemo(() => {
    const styles: CustomSquareStyles = {};
    if (preview.lastMove) {
      styles[preview.lastMove.from as Square] = { backgroundColor: "rgba(229, 143, 42, 0.48)" };
      styles[preview.lastMove.to as Square] = { backgroundColor: "rgba(229, 143, 42, 0.72)" };
    }
    if (preview.checkedKingSquare) {
      styles[preview.checkedKingSquare as Square] = { backgroundColor: "rgba(220, 38, 38, 0.68)" };
    }
    return styles;
  }, [preview.lastMove?.from, preview.lastMove?.to, preview.checkedKingSquare]);

  const ariaLabel = `${preview.white} versus ${preview.black}, ${preview.resultLabel}${
    preview.termination ? `, ${preview.termination}` : ""
  }`;

  return (
    <MiniBoardFrame role="img" aria-label={ariaLabel}>
      <Chessboard
        position={preview.fen}
        boardOrientation="white"
        boardWidth={112}
        customPieces={MINI_PIECES}
        customSquareStyles={squareStyles}
        customDarkSquareStyle={{ backgroundColor: "#B98763" }}
        customLightSquareStyle={{ backgroundColor: "#EDD6B1" }}
        customBoardStyle={{ borderRadius: 3 }}
        animationDuration={0}
        arePiecesDraggable={false}
        showBoardNotation={false}
      />
    </MiniBoardFrame>
  );
}

function Spinner() {
  return <SpinnerMark aria-hidden="true" />;
}

function CheckIcon() {
  return <CheckSvg aria-hidden="true" viewBox="0 0 16 16" strokeWidth="2"><path d="m3 8 3 3 7-7" /></CheckSvg>;
}

function AlertIcon({ small = false }: { small?: boolean }) {
  return <AlertSvg aria-hidden="true" viewBox="0 0 24 24" $small={small} fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v4m0 4h.01M10.3 3.8 2.4 18a2 2 0 0 0 1.75 3h15.7a2 2 0 0 0 1.75-3L13.7 3.8a2 2 0 0 0-3.4 0Z" strokeLinecap="round" strokeLinejoin="round" /></AlertSvg>;
}

function PawnIcon() {
  return <PawnSvg aria-hidden="true" viewBox="0 0 24 24" strokeWidth="1.8"><path d="M9 8a3 3 0 1 1 6 0c0 1.2-.7 2.25-1.7 2.72.2 2.02 1.1 3.57 2.7 4.78H8c1.6-1.2 2.5-2.76 2.7-4.78A3 3 0 0 1 9 8Zm-2 7.5h10l1 4H6l1-4Z" strokeLinejoin="round" /></PawnSvg>;
}

function BookIcon() {
  return <BookSvg aria-hidden="true" viewBox="0 0 20 20" strokeWidth="1.6"><path d="M2.5 4.5c2.8-.7 5-.2 7 1.4v10c-2-1.6-4.2-2.1-7-1.4v-10Zm15 0c-2.8-.7-5-.2-7 1.4v10c2-1.6 4.2-2.1 7-1.4v-10Z" strokeLinejoin="round" /></BookSvg>;
}

function CalendarIcon() {
  return <CalendarSvg aria-hidden="true" viewBox="0 0 20 20" strokeWidth="1.6"><rect x="2.5" y="4" width="15" height="13" rx="2" /><path d="M6 2v4m8-4v4M2.5 8h15" /></CalendarSvg>;
}
