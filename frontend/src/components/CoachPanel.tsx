import type { Classification } from "../types";
import { iconUrl } from "../api/client";
import { BADGE_COLORS } from "../constants";

interface CoachPanelProps {
  summary: string;
  comment: string;
  headline?: string;
  classification?: Classification | null;
  bestLine?: string[];
}

export default function CoachPanel({
  summary,
  comment,
  headline,
  classification,
  bestLine,
}: CoachPanelProps) {
  const color = classification ? BADGE_COLORS[classification] : undefined;

  return (
    <div className="bg-white text-[#2b2b2b] rounded-2xl p-4 shadow-lg leading-relaxed">
      {classification && color && (
        <div className="mb-2 inline-flex items-center gap-1.5">
          <img src={iconUrl(classification)} alt={classification} className="w-5 h-5" />
          <span
            className="text-white text-xs font-extrabold px-2.5 py-0.5 rounded-full"
            style={{ background: color }}
          >
            {classification}
          </span>
        </div>
      )}
      {headline && <div className="font-bold mb-1" dangerouslySetInnerHTML={{ __html: headline }} />}
      <div>{comment || summary}</div>
      {bestLine && bestLine.length > 0 && (
        <div className="mt-3 text-sm text-gray-600 border-t pt-2">
          <span className="font-semibold">Best line: </span>
          {bestLine.join(" ")}
        </div>
      )}
    </div>
  );
}
