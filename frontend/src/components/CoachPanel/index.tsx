import type { Classification } from "../../types";
import { iconUrl } from "../../api/client";
import { BADGE_COLORS } from "../../constants";
import {
  Badge,
  BadgeIcon,
  BadgeRow,
  BestLine,
  BestLineLabel,
  ErrorMessage,
  LoadingMessage,
  LoadingSpinner,
  Panel,
} from "./styledcomponents";

interface CoachPanelProps {
  summary: string;
  comment: string;
  classification?: Classification | null;
  bestLine?: string[];
  loading?: boolean;
  error?: string | null;
}

export default function CoachPanel({
  summary,
  comment,
  classification,
  bestLine,
  loading = false,
  error = null,
}: CoachPanelProps) {
  const color = classification ? BADGE_COLORS[classification] : undefined;

  return (
    <Panel>
      {classification && color && (
        <BadgeRow>
          <BadgeIcon src={iconUrl(classification)} alt={classification} />
          <Badge $color={color}>
            {classification}
          </Badge>
        </BadgeRow>
      )}
      {loading ? (
        <LoadingMessage>
          <LoadingSpinner />
          Looking at this move…
        </LoadingMessage>
      ) : error ? (
        <ErrorMessage>{error}</ErrorMessage>
      ) : (
        <div>{comment || summary}</div>
      )}
      {bestLine && bestLine.length > 0 && (
        <BestLine>
          <BestLineLabel>Best line: </BestLineLabel>
          {bestLine.join(" ")}
        </BestLine>
      )}
    </Panel>
  );
}
