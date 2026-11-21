import styled, { css, keyframes } from "styled-components";

const spin = keyframes`
  to { transform: rotate(360deg); }
`;

const progress = keyframes`
  from { transform: translateX(-110%); }
  to { transform: translateX(365%); }
`;

export const MiniPieceImage = styled.img<{ $size: number }>`
  width: ${({ $size }) => $size}px;
  height: ${({ $size }) => $size}px;
`;

export const Slot = styled.div`
  min-width: 0;
  height: 9rem;
  min-height: 9rem;
`;

const stateBox = css`
  display: flex;
  height: 100%;
  align-items: center;
  border-radius: 0.75rem;
  padding-right: 1.25rem;
  padding-left: 1.25rem;
`;

export const EmptyBox = styled.div`
  ${stateBox};
  border: 1px dashed #55514c;
  background: rgb(39 37 34 / 0.4);
`;

export const InvalidBox = styled.div`
  ${stateBox};
  border: 1px solid #991b1b;
  background: rgb(69 10 10 / 0.15);
`;

const iconShell = css`
  margin-right: 1rem;
  display: grid;
  width: 2.75rem;
  height: 2.75rem;
  flex-shrink: 0;
  place-items: center;
  border-radius: 9999px;
`;

export const EmptyIconShell = styled.span`
  ${iconShell};
  background: #21201d;
  color: #77716a;
`;

export const InvalidIconShell = styled.span`
  ${iconShell};
  background: rgb(69 10 10 / 0.7);
  color: #f87171;
`;

export const StateCopy = styled.div<{ $constrained?: boolean }>`
  min-width: ${({ $constrained }) => ($constrained ? "0" : "auto")};
`;

export const StateTitle = styled.p`
  color: #f2f1ed;
  font-weight: 600;
`;

export const StateDescription = styled.p<{ $invalid?: boolean }>`
  margin-top: 0.25rem;
  color: ${({ $invalid }) => ($invalid ? "#d8d2ca" : "#9a948b")};
  font-size: 0.875rem;
  line-height: 1.25rem;

  ${({ $invalid }) =>
    $invalid &&
    css`
      overflow: hidden;
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 2;
    `}
`;

export const Preview = styled.div<{ $failed: boolean }>`
  position: relative;
  display: flex;
  height: 100%;
  min-width: 0;
  overflow: hidden;
  border: 1px solid ${({ $failed }) => ($failed ? "#991b1b" : "#403e3b")};
  border-radius: 0.75rem;
  background: #21201d;
  padding: 1rem;
`;

export const PreviewCopy = styled.div`
  margin-left: 1rem;
  display: flex;
  min-width: 0;
  flex: 1 1 0%;
  flex-direction: column;
  justify-content: space-between;
  padding-top: 0.125rem;
  padding-bottom: 0.125rem;
`;

export const PreviewHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
`;

export const PreviewLabel = styled.span`
  color: #c9c3ba;
  font-size: 0.875rem;
  line-height: 1.25rem;
  font-weight: 600;
`;

export const Players = styled.div`
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 0.5rem;
`;

export const Versus = styled.span`
  flex-shrink: 0;
  color: #77716a;
  font-size: 0.75rem;
  line-height: 1rem;
`;

export const Result = styled.span`
  margin-left: auto;
  flex-shrink: 0;
  border: 1px solid #403e3b;
  border-radius: 9999px;
  padding: 0.125rem 0.5rem;
  color: #eeeae3;
  font-size: 0.75rem;
  line-height: 1rem;
  font-weight: 600;
`;

export const OpeningRow = styled.div`
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  line-height: 1.25rem;
`;

export const OpeningName = styled.span<{ $recognized: boolean }>`
  overflow: hidden;
  color: ${({ $recognized }) => ($recognized ? "#eeeae3" : "#77716a")};
  text-overflow: ellipsis;
  white-space: nowrap;
`;

export const Eco = styled.span`
  flex-shrink: 0;
  border: 1px solid #403e3b;
  border-radius: 0.25rem;
  padding: 0.125rem 0.375rem;
  color: #b6b0a7;
  font-size: 11px;
`;

export const MetaRow = styled.div`
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 0.5rem;
  color: #aaa49c;
  font-size: 0.75rem;
  line-height: 1rem;
`;

export const TruncatedMeta = styled.span<{ $tone?: "error" | "success" }>`
  overflow: hidden;
  color: ${({ $tone }) =>
    $tone === "error" ? "#fca5a5" : $tone === "success" ? "#86efac" : "inherit"};
  text-overflow: ellipsis;
  white-space: nowrap;
`;

export const CompletionStatus = styled.span<{ $succeeded: boolean }>`
  color: ${({ $succeeded }) => ($succeeded ? "#86efac" : "#fca5a5")};
`;

export const PlayerName = styled.span`
  display: flex;
  min-width: 0;
  max-width: 35%;
  align-items: center;
  gap: 0.375rem;
`;

export const PlayerMarker = styled.span<{ $color: "white" | "black" }>`
  width: 0.875rem;
  height: 0.875rem;
  flex-shrink: 0;
  border: 1px solid ${({ $color }) => ($color === "white" ? "#d8d7d2" : "#779556")};
  border-radius: 3px;
  background: ${({ $color }) => ($color === "white" ? "#EBECD0" : "#779556")};
`;

export const PlayerText = styled.span`
  overflow: hidden;
  color: #f2f1ed;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
`;

export const Elo = styled.span`
  flex-shrink: 0;
  color: #77716a;
  font-size: 0.75rem;
  line-height: 1rem;
`;

type PillKind = "running" | "failed" | "completed" | "valid";

const pillColors: Record<PillKind, { background: string; color: string }> = {
  running: { background: "rgb(229 143 42 / 0.15)", color: "#e58f2a" },
  failed: { background: "rgb(69 10 10 / 0.7)", color: "#f87171" },
  completed: { background: "rgb(5 46 22 / 0.7)", color: "#4ade80" },
  valid: { background: "rgb(5 46 22 / 0.7)", color: "#4ade80" },
};

export const StatusPillElement = styled.span<{ $kind: PillKind }>`
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 0.375rem;
  border-radius: 9999px;
  background: ${({ $kind }) => pillColors[$kind].background};
  padding: 0.25rem 0.625rem;
  color: ${({ $kind }) => pillColors[$kind].color};
  font-size: 0.75rem;
  line-height: 1rem;
  font-weight: 600;
`;

export const ProgressTrack = styled.div`
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  height: 0.25rem;
  background: #4b4741;
`;

export const ProgressFill = styled.div<{ $percent: number | null }>`
  height: 100%;
  width: ${({ $percent }) => ($percent === null ? "38%" : `${$percent}%`)};
  background: #e58f2a;
  ${({ $percent }) =>
    $percent === null
      ? css`
          animation: ${progress} 1.2s ease-in-out infinite;
        `
      : css`
          transition: width 150ms cubic-bezier(0.4, 0, 0.2, 1);
        `}
`;

export const MiniBoardFrame = styled.div`
  width: 7rem;
  height: 7rem;
  flex-shrink: 0;
  overflow: hidden;
  border-radius: 0.25rem;
`;

export const SpinnerMark = styled.span`
  width: 0.75rem;
  height: 0.75rem;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 9999px;
  animation: ${spin} 1s linear infinite;
`;

export const CheckSvg = styled.svg`
  width: 0.875rem;
  height: 0.875rem;
  fill: none;
  stroke: currentColor;
`;

export const AlertSvg = styled.svg<{ $small: boolean }>`
  width: ${({ $small }) => ($small ? "0.875rem" : "1.5rem")};
  height: ${({ $small }) => ($small ? "0.875rem" : "1.5rem")};
`;

export const PawnSvg = styled.svg`
  width: 1.5rem;
  height: 1.5rem;
  fill: none;
  stroke: currentColor;
`;

export const BookSvg = styled.svg`
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
  fill: none;
  stroke: #aaa49c;
`;

export const CalendarSvg = styled.svg`
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
  fill: none;
  stroke: currentColor;
`;
