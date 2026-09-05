import type { Classification } from "../types";
import { iconUrl } from "../api/client";
import { BADGE_COLORS } from "../constants";

interface CoachPanelProps {
  summary: string;
  comment: string;
  headline?: string;
  classification?: Classification | null;
  bestLine?: string[];
  loading?: boolean;
  error?: string | null;
}

export default function CoachPanel({
  summary,
  comment,
  headline,
  classification,
  bestLine,
  loading = false,
  error = null,
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
      {loading ? (
        <div className="flex items-center gap-2 text-gray-500">
          <span className="w-4 h-4 rounded-full border-2 border-gray-400 border-t-transparent animate-spin" />
          Looking at this move…
        </div>
      ) : error ? (
        <div className="text-red-600">{error}</div>
      ) : (
        <div>{comment || summary}</div>
      )}
      {bestLine && bestLine.length > 0 && (
        <div className="mt-3 text-sm text-gray-600 border-t pt-2">
          <span className="font-semibold">Best line: </span>
          {bestLine.join(" ")}
        </div>
      )}
    </div>
  );
}
