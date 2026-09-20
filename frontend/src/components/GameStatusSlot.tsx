import { useMemo } from "react";
import { Chessboard } from "react-chessboard";
import type { CustomPieces, CustomSquareStyles, Piece, Square } from "react-chessboard/dist/chessboard/types";
import type { GamePreview, PgnParseState } from "../pgnPreview";
import type { CommentaryStatus } from "../types";

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
          <img
            src={`/pieces/${color === "w" ? "White" : "Black"}-${name}.png`}
            alt=""
            draggable={false}
            style={{ width: squareWidth, height: squareWidth }}
          />
        ),
      ];
    })
  )
) as CustomPieces;

export default function GameStatusSlot({ state }: GameStatusSlotProps) {
  return (
    <div aria-live="polite" aria-atomic="true" className="h-36 min-h-36 min-w-0">
      {state.kind === "empty" && <EmptyState />}
      {state.kind === "invalid" && <InvalidState reason={state.reason} />}
      {(state.kind === "valid" || state.kind === "running" || state.kind === "failed" || state.kind === "completed") && (
        <PreviewCard state={state} />
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full items-center rounded-xl border border-dashed border-[#55514c] bg-[#272522]/40 px-5">
      <span className="mr-4 grid h-11 w-11 shrink-0 place-items-center rounded-full bg-[#21201d] text-[#77716a]">
        <PawnIcon />
      </span>
      <div>
        <p className="font-semibold text-[#f2f1ed]">Paste a PGN to preview the game</p>
        <p className="mt-1 text-sm text-[#9a948b]">Players, result, and opening show up here.</p>
      </div>
    </div>
  );
}

function InvalidState({ reason }: { reason: string }) {
  return (
    <div className="flex h-full items-center rounded-xl border border-red-800 bg-red-950/15 px-5">
      <span className="mr-4 grid h-11 w-11 shrink-0 place-items-center rounded-full bg-red-950/70 text-red-400">
        <AlertIcon />
      </span>
      <div className="min-w-0">
        <p className="font-semibold text-[#f2f1ed]">Couldn&apos;t read this game</p>
        <p className="mt-1 line-clamp-2 text-sm text-[#d8d2ca]">{reason}</p>
      </div>
    </div>
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
    <div
      className={`relative flex h-full min-w-0 overflow-hidden rounded-xl border bg-[#21201d] p-4 ${
        state.kind === "failed" ? "border-red-800" : "border-panelBorder"
      }`}
    >
      <MiniBoard preview={preview} />

      <div className="ml-4 flex min-w-0 flex-1 flex-col justify-between py-0.5">
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm font-semibold text-[#c9c3ba]">
            Game preview
          </span>
          <StatusPill kind={state.kind} />
        </div>

        <div className="flex min-w-0 items-center gap-2">
          <Player color="white" name={preview.white} elo={preview.whiteElo} />
          <span className="shrink-0 text-xs text-[#77716a]">vs</span>
          <Player color="black" name={preview.black} elo={preview.blackElo} />
          <span className="ml-auto shrink-0 rounded-full border border-panelBorder px-2 py-0.5 text-xs font-semibold text-[#eeeae3]">
            {preview.resultLabel}
          </span>
        </div>

        <div className="flex min-w-0 items-center gap-2 text-sm">
          <BookIcon />
          <span className={`truncate ${preview.opening ? "text-[#eeeae3]" : "text-[#77716a]"}`} title={preview.opening}>
            {preview.opening ?? "Opening not recognized"}
          </span>
          {preview.eco && (
            <span className="shrink-0 rounded border border-panelBorder px-1.5 py-0.5 text-[11px] text-[#b6b0a7]">
              {preview.eco}
            </span>
          )}
        </div>

        <div className="flex min-w-0 items-center gap-2 text-xs text-[#aaa49c]">
          <CalendarIcon />
          {state.kind === "running" ? (
            <span>
              {state.progress?.total
                ? `Analyzing move ${state.progress.ply} of ${state.progress.total}`
                : "Analyzing…"}
            </span>
          ) : state.kind === "failed" ? (
            <span className="truncate text-red-300" title={state.reason}>{state.reason}</span>
          ) : state.kind === "completed" ? (
            <span className={geminiSucceeded ? "text-green-300" : "text-red-300"}>
              {geminiSucceeded ? "Status: Success" : "Status: Failure"}
            </span>
          ) : (
            <span className="truncate" title={meta.join(" · ")}>{meta.join(" · ")}</span>
          )}
        </div>
      </div>

      {state.kind === "running" && (
        <div className="absolute inset-x-0 bottom-0 h-1 bg-[#4b4741]">
          <div
            className={`h-full bg-accent ${progressPercent === null ? "status-progress-indeterminate" : "transition-[width]"}`}
            style={progressPercent === null ? undefined : { width: `${progressPercent}%` }}
          />
        </div>
      )}
    </div>
  );
}

function geminiRespondedSuccessfully(succeeded: boolean, status?: CommentaryStatus) {
  if (!status) return succeeded;
  return status.gemini_attempted && status.generation_complete;
}

function Player({ color, name, elo }: { color: "white" | "black"; name: string; elo?: string }) {
  const title = elo ? `${name} (${elo})` : name;
  return (
    <span
      className="flex min-w-0 max-w-[35%] items-center gap-1.5"
      title={title}
    >
      <span
        aria-hidden="true"
        className={`h-3.5 w-3.5 shrink-0 rounded-[3px] border ${
          color === "white" ? "border-[#d8d7d2] bg-boardLight" : "border-boardDark bg-boardDark"
        }`}
      />
      <span className="truncate font-semibold text-[#f2f1ed]">{name}</span>
      {elo && <span className="shrink-0 text-xs text-[#77716a]">{elo}</span>}
    </span>
  );
}

function StatusPill({ kind }: { kind: "valid" | "running" | "failed" | "completed" }) {
  if (kind === "running") {
    return (
      <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-accent/15 px-2.5 py-1 text-xs font-semibold text-accent">
        <Spinner /> Analyzing
      </span>
    );
  }
  if (kind === "failed") {
    return (
      <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-red-950/70 px-2.5 py-1 text-xs font-semibold text-red-400">
        <AlertIcon small /> Review failed
      </span>
    );
  }
  if (kind === "completed") {
    return (
      <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-green-950/70 px-2.5 py-1 text-xs font-semibold text-green-400">
        <CheckIcon /> Review complete
      </span>
    );
  }
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-green-950/70 px-2.5 py-1 text-xs font-semibold text-green-400">
      <CheckIcon /> PGN valid
    </span>
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
    <div className="h-28 w-28 shrink-0 overflow-hidden rounded" role="img" aria-label={ariaLabel}>
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
    </div>
  );
}

function Spinner() {
  return <span aria-hidden="true" className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />;
}

function CheckIcon() {
  return <svg aria-hidden="true" viewBox="0 0 16 16" className="h-3.5 w-3.5 fill-none stroke-current" strokeWidth="2"><path d="m3 8 3 3 7-7" /></svg>;
}

function AlertIcon({ small = false }: { small?: boolean }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className={small ? "h-3.5 w-3.5" : "h-6 w-6"} fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 9v4m0 4h.01M10.3 3.8 2.4 18a2 2 0 0 0 1.75 3h15.7a2 2 0 0 0 1.75-3L13.7 3.8a2 2 0 0 0-3.4 0Z" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

function PawnIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className="h-6 w-6 fill-none stroke-current" strokeWidth="1.8"><path d="M9 8a3 3 0 1 1 6 0c0 1.2-.7 2.25-1.7 2.72.2 2.02 1.1 3.57 2.7 4.78H8c1.6-1.2 2.5-2.76 2.7-4.78A3 3 0 0 1 9 8Zm-2 7.5h10l1 4H6l1-4Z" strokeLinejoin="round" /></svg>;
}

function BookIcon() {
  return <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4 shrink-0 fill-none stroke-[#aaa49c]" strokeWidth="1.6"><path d="M2.5 4.5c2.8-.7 5-.2 7 1.4v10c-2-1.6-4.2-2.1-7-1.4v-10Zm15 0c-2.8-.7-5-.2-7 1.4v10c2-1.6 4.2-2.1 7-1.4v-10Z" strokeLinejoin="round" /></svg>;
}

function CalendarIcon() {
  return <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4 shrink-0 fill-none stroke-current" strokeWidth="1.6"><rect x="2.5" y="4" width="15" height="13" rx="2" /><path d="M6 2v4m8-4v4M2.5 8h15" /></svg>;
}
