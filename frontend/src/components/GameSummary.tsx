import type { AnalysisResult, Classification, MoveData } from "../types";
import { iconUrl } from "../api/client";
import { BADGE_COLORS, SUMMARY_ORDER } from "../constants";

/** Shared column template so the pinned rating footer lines up with the rows above it. */
const ROW_GRID = "grid grid-cols-[1fr_6.5rem_2rem_6.5rem] items-center gap-x-2";

function ScoreBox({ value, dark }: { value: string; dark?: boolean }) {
  return (
    <span
      className={`block text-center font-bold rounded px-2 py-1.5 ${
        dark ? "bg-[#262522] text-[#e8e8e8]" : "bg-[#f5f5f0] text-[#262522]"
      }`}
    >
      {value}
    </span>
  );
}

function classCounts(moves: MoveData[]) {
  const counts = {} as Record<Classification, { White: number; Black: number }>;
  for (const c of SUMMARY_ORDER) counts[c] = { White: 0, Black: 0 };
  for (const m of moves) {
    const row = counts[m.classification];
    if (row) row[m.turn] += 1;
  }
  return counts;
}

export default function GameSummary({ result }: { result: AnalysisResult }) {
  const counts = classCounts(result.move_data);

  return (
    <div className="text-base">
      <div className={`${ROW_GRID} text-sm text-[#8b8987] font-semibold mb-2`}>
        <span />
        <span className="text-center truncate" title={result.meta.White}>
          {result.meta.White}
        </span>
        <span />
        <span className="text-center truncate" title={result.meta.Black}>
          {result.meta.Black}
        </span>
      </div>

      <div className={`${ROW_GRID} mb-3`}>
        <span>Accuracy</span>
        <ScoreBox value={result.stats.White.accuracy.toFixed(1)} />
        <span />
        <ScoreBox value={result.stats.Black.accuracy.toFixed(1)} dark />
      </div>

      <div className="border-t border-panelBorder mb-1" />

      {SUMMARY_ORDER.map((c) => (
        <div key={c} className={`${ROW_GRID} py-1.5`}>
          <span style={{ color: BADGE_COLORS[c] }}>{c}</span>
          <span className="text-center font-semibold" style={{ color: BADGE_COLORS[c] }}>
            {counts[c].White}
          </span>
          <img src={iconUrl(c)} alt={c} title={c} className="w-6 h-6 justify-self-center" />
          <span className="text-center font-semibold" style={{ color: BADGE_COLORS[c] }}>
            {counts[c].Black}
          </span>
        </div>
      ))}
    </div>
  );
}

export function RatingFooter({ result }: { result: AnalysisResult }) {
  return (
    <div className={`${ROW_GRID} border-t border-panelBorder pt-3 text-base`}>
      <span className="text-[#b9b7b4] leading-tight">
        Estimated
        <br />
        Performance
      </span>
      <ScoreBox value={String(result.stats.White.rating)} />
      <span />
      <ScoreBox value={String(result.stats.Black.rating)} dark />
    </div>
  );
}
