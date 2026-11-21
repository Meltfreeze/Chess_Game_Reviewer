import type { AnalysisResult, Classification, MoveData } from "../../types";
import { iconUrl } from "../../api/client";
import { BADGE_COLORS, SUMMARY_ORDER } from "../../constants";
import {
  AccuracyRow,
  ClassificationCount,
  ClassificationIcon,
  ClassificationLabel,
  ClassificationRow,
  Divider,
  HeaderRow,
  PlayerName,
  RatingLabel,
  RatingRow,
  Score,
  Summary,
} from "./styledcomponents";

function ScoreBox({ value, dark }: { value: string; dark?: boolean }) {
  return <Score $dark={dark}>{value}</Score>;
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
    <Summary>
      <HeaderRow>
        <span />
        <PlayerName title={result.meta.White}>
          {result.meta.White}
        </PlayerName>
        <span />
        <PlayerName title={result.meta.Black}>
          {result.meta.Black}
        </PlayerName>
      </HeaderRow>

      <AccuracyRow>
        <span>Accuracy</span>
        <ScoreBox value={result.stats.White.accuracy.toFixed(1)} />
        <span />
        <ScoreBox value={result.stats.Black.accuracy.toFixed(1)} dark />
      </AccuracyRow>

      <Divider />

      {SUMMARY_ORDER.map((c) => (
        <ClassificationRow key={c}>
          <ClassificationLabel $color={BADGE_COLORS[c]}>{c}</ClassificationLabel>
          <ClassificationCount $color={BADGE_COLORS[c]}>
            {counts[c].White}
          </ClassificationCount>
          <ClassificationIcon src={iconUrl(c)} alt={c} title={c} />
          <ClassificationCount $color={BADGE_COLORS[c]}>
            {counts[c].Black}
          </ClassificationCount>
        </ClassificationRow>
      ))}
    </Summary>
  );
}

export function RatingFooter({ result }: { result: AnalysisResult }) {
  return (
    <RatingRow>
      <RatingLabel>
        Estimated
        <br />
        Performance
      </RatingLabel>
      <ScoreBox value={String(result.stats.White.rating)} />
      <span />
      <ScoreBox value={String(result.stats.Black.rating)} dark />
    </RatingRow>
  );
}
