import { cpToWinPercent } from "../api/client";

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
    <div
      className="rounded overflow-hidden shadow-inner"
      style={{ width: 26, height, background: "#403e3b", position: "relative" }}
    >
      <div
        data-testid="eval-bar-white-fill"
        className="eval-bar-transition absolute w-full"
        style={{
          height: whiteHeight,
          background: "#f5f5f0",
          top: flipped ? 0 : undefined,
          bottom: flipped ? undefined : 0,
        }}
      />
      <span
        className="absolute w-full text-center select-none pointer-events-none"
        style={{
          left: 0,
          top: labelAtBottom ? undefined : 3,
          bottom: labelAtBottom ? 3 : undefined,
          fontSize: 10,
          fontWeight: 700,
          lineHeight: 1,
          letterSpacing: "-0.03em",
          color: whiteAhead ? "#403e3b" : "#f5f5f0",
        }}
      >
        {label}
      </span>
    </div>
  );
}
