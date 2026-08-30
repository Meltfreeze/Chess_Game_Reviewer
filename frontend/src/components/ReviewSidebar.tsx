import { useState } from "react";
import type { ReactNode } from "react";
import type { AnalysisResult, MoveData } from "../types";
import EvalGraph from "./EvalGraph";
import CoachPanel from "./CoachPanel";
import MoveList from "./MoveList";
import GameSummary, { RatingFooter } from "./GameSummary";

type Tab = "review" | "moves";

interface ReviewSidebarProps {
  result: AnalysisResult;
  currentPly: number;
  currentMove: MoveData | null;
  comment: string;
  onSelect: (ply: number) => void;
  height: number;
}

export default function ReviewSidebar({
  result,
  currentPly,
  currentMove,
  comment,
  onSelect,
  height,
}: ReviewSidebarProps) {
  const [tab, setTab] = useState<Tab>("review");

  return (
    <div
      className="bg-panel border border-panelBorder rounded-xl flex flex-col overflow-hidden"
      style={{ height }}
    >
      {/* Coach comment and graph stay visible in both tabs — both track the selected move. */}
      <div className="shrink-0 p-3 pb-0">
        <CoachPanel
          summary={result.coach.summary}
          comment={comment}
          classification={currentMove?.classification ?? null}
          bestLine={currentMove?.best_line}
        />
        <div className="mt-3">
          <EvalGraph history={result.hist} currentPly={currentPly} onSelect={onSelect} />
        </div>
      </div>

      <div className="shrink-0 flex gap-1 px-3 pt-3">
        <TabButton active={tab === "review"} onClick={() => setTab("review")}>
          Review
        </TabButton>
        <TabButton active={tab === "moves"} onClick={() => setTab("moves")}>
          Moves
        </TabButton>
      </div>

      <div className="panel-scroll flex-1 min-h-0 overflow-y-auto px-3 py-3">
        {tab === "review" ? (
          <GameSummary result={result} />
        ) : (
          <MoveList moves={result.move_data} currentPly={currentPly} onSelect={onSelect} />
        )}
      </div>

      {tab === "review" && (
        <div className="shrink-0 px-3 pb-3">
          <RatingFooter result={result} />
        </div>
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1.5 rounded-md text-base font-semibold ${
        active ? "bg-panelBorder text-white" : "text-[#8b8987] hover:text-[#e8e8e8]"
      }`}
    >
      {children}
    </button>
  );
}
