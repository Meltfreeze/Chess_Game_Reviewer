import { cpToWinPercent } from "../api/client";

interface EvalBarProps {
  evalCpWhite: number;
  height?: number;
}

export default function EvalBar({ evalCpWhite, height = 520 }: EvalBarProps) {
  const wp = cpToWinPercent(evalCpWhite);
  const whiteHeight = Math.round(wp * height);

  return (
    <div
      className="rounded overflow-hidden shadow-inner"
      style={{
        width: 26,
        height,
        background: "#403e3b",
        position: "relative",
      }}
    >
      <div
        className="eval-bar-transition absolute bottom-0 w-full"
        style={{
          height: whiteHeight,
          background: "#f5f5f0",
        }}
      />
    </div>
  );
}
