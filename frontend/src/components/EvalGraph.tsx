interface EvalGraphProps {
  history: number[];
  currentPly: number;
  onSelect?: (ply: number) => void;
}

export default function EvalGraph({ history, currentPly, onSelect }: EvalGraphProps) {
  const W = 100;
  const H = 46;

  const pts = history.map((v, i) => {
    const x = (i / Math.max(1, history.length - 1)) * W;
    const y = H / 2 - (Math.max(-6, Math.min(6, v)) / 6) * (H / 2);
    return { x, y, ply: i };
  });

  const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const area =
    `M0,${H / 2} ` +
    pts.map((p) => `L${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ") +
    ` L${W},${H / 2} Z`;

  const cursorX = pts[Math.min(currentPly, pts.length - 1)]?.x ?? 0;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className="w-full h-[70px] bg-panelBorder rounded-md cursor-pointer"
      onClick={(e) => {
        if (!onSelect) return;
        const rect = e.currentTarget.getBoundingClientRect();
        const ratio = (e.clientX - rect.left) / rect.width;
        const ply = Math.round(ratio * (history.length - 1));
        onSelect(Math.max(0, Math.min(history.length - 1, ply)));
      }}
    >
      <line x1="0" y1={H / 2} x2={W} y2={H / 2} stroke="#5c5a57" strokeWidth="0.4" />
      <path d={area} fill="#f5f5f0" fillOpacity="0.85" />
      <path d={path} fill="none" stroke="#9c9a97" strokeWidth="0.5" />
      <line x1={cursorX} y1="0" x2={cursorX} y2={H} stroke="#e58f2a" strokeWidth="0.6" />
    </svg>
  );
}
