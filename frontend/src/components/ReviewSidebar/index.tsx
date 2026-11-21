import { useState } from "react";
import type { ReactNode } from "react";
import type { AnalysisResult } from "../../types";
import { currentNode, type MoveTree } from "../../moveTree";
import EvalGraph from "../EvalGraph";
import CoachPanel from "../CoachPanel";
import MoveList from "../MoveList";
import GameSummary, { RatingFooter } from "../GameSummary";
import {
  Footer,
  GraphSection,
  ScrollArea,
  Sidebar,
  TabButtonElement,
  Tabs,
  TopSection,
} from "./styledcomponents";

type Tab = "review" | "moves";

interface ReviewSidebarProps {
  result: AnalysisResult;
  tree: MoveTree;
  /** Main-line ply the eval-graph cursor should sit on. */
  currentPly: number;
  onSelectPly: (ply: number) => void;
  onSelectNode: (nodeId: string) => void;
}

export default function ReviewSidebar({
  result,
  tree,
  currentPly,
  onSelectPly,
  onSelectNode,
}: ReviewSidebarProps) {
  const [tab, setTab] = useState<Tab>("review");
  const node = currentNode(tree);

  return (
    <Sidebar>
      <TopSection>
        <CoachPanel
          summary={result.coach.summary}
          comment={node.comment}
          classification={node.data?.classification ?? null}
          bestLine={node.data?.best_line}
          loading={node.status === "pending"}
          error={node.status === "error" ? node.error : null}
        />
        <GraphSection>
          <EvalGraph history={result.hist} currentPly={currentPly} onSelect={onSelectPly} />
        </GraphSection>
      </TopSection>

      <Tabs>
        <TabButton active={tab === "review"} onClick={() => setTab("review")}>
          Review
        </TabButton>
        <TabButton active={tab === "moves"} onClick={() => setTab("moves")}>
          Moves
        </TabButton>
      </Tabs>

      <ScrollArea>
        {tab === "review" ? (
          <GameSummary result={result} />
        ) : (
          <MoveList tree={tree} onSelect={onSelectNode} />
        )}
      </ScrollArea>

      {tab === "review" && (
        <Footer>
          <RatingFooter result={result} />
        </Footer>
      )}
    </Sidebar>
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
    <TabButtonElement
      type="button"
      onClick={onClick}
      $active={active}
    >
      {children}
    </TabButtonElement>
  );
}
