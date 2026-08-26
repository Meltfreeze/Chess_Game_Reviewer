import { cpToWinPercent } from "../api/client";

interface EvalBarProps {
  evalCpWhite: number;
  evalText?: string;
  height?: number;
}

function formatEvalLabel(evalCpWhite: number, evalText?: string): string {
  if (evalText && evalText.startsWith("#")) {
    const n = Math.abs(parseInt(evalText.slice(1), 10));
    return n ? `M${n}` : "M";
  }
  if (Math.abs(evalCpWhite) >= 10000) return "M";
  return (Math.abs(evalCpWhite) / 100).toFixed(1);
}

export default function EvalBar({ evalCpWhite, evalText, height = 520 }: EvalBarProps) {
  const wp = cpToWinPercent(evalCpWhite);
  const whiteHeight = Math.round(wp * height);
  const whiteAhead = evalCpWhite >= 0;
  const label = formatEvalLabel(evalCpWhite, evalText);

  return (
    <div
      className="rounded overflow-hidden shadow-inner"
      style={{ width: 26, height, background: "#403e3b", position: "relative" }}
    >
      <div
        className="eval-bar-transition absolute bottom-0 w-full"
        style={{ height: whiteHeight, background: "#f5f5f0" }}
      />
      <span
        className="absolute w-full text-center select-none pointer-events-none"
        style={{
          left: 0,
          top: whiteAhead ? undefined : 3,
          bottom: whiteAhead ? 3 : undefined,
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
