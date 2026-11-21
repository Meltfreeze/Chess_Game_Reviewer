import { cpToWinPercent } from "../../api/client";
import { Bar, EvalLabel, WhiteFill } from "./styledcomponents";

interface EvalBarProps {
  evalCpWhite: number;
  evalText?: string;
  height?: number;
  flipped?: boolean;
}

function formatEvalLabel(evalCpWhite: number, evalText?: string): string {
  if (evalText && evalText.startsWith("#")) {
    const n = Math.abs(parseInt(evalText.slice(1), 10));
    return n ? `M${n}` : "M";
  }
  if (Math.abs(evalCpWhite) >= 10000) return "M";
  return (Math.abs(evalCpWhite) / 100).toFixed(1);
}

export default function EvalBar({
  evalCpWhite,
  evalText,
  height = 520,
  flipped = false,
}: EvalBarProps) {
  const wp = cpToWinPercent(evalCpWhite);
  const whiteHeight = Math.round(wp * height);
  const whiteAhead = evalCpWhite >= 0;
  const labelAtBottom = whiteAhead !== flipped;
  const label = formatEvalLabel(evalCpWhite, evalText);

  return (
    <Bar $height={height}>
      <WhiteFill
        data-testid="eval-bar-white-fill"
        $height={whiteHeight}
        $flipped={flipped}
      />
      <EvalLabel $atBottom={labelAtBottom} $whiteAhead={whiteAhead}>
        {label}
      </EvalLabel>
    </Bar>
  );
}
