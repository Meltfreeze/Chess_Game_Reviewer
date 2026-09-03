import type { ReactNode } from "react";

interface MoveNavProps {
  currentPly: number;
  totalPlies: number;
  onSelect: (ply: number) => void;
}

export default function MoveNav({ currentPly, totalPlies, onSelect }: MoveNavProps) {
  const atStart = currentPly <= 0;
  const atEnd = currentPly >= totalPlies;

  return (
    <div className="shrink-0 bg-panel border border-panelBorder rounded-xl p-2 flex gap-2">
      <NavButton label="First move" disabled={atStart} onClick={() => onSelect(0)}>
        <path d="M6.5 5v14" />
        <path d="M17.5 5l-7 7 7 7" />
      </NavButton>
      <NavButton label="Previous move" disabled={atStart} onClick={() => onSelect(currentPly - 1)}>
        <path d="M15.5 5l-7 7 7 7" />
      </NavButton>
      <NavButton label="Next move" disabled={atEnd} onClick={() => onSelect(currentPly + 1)}>
        <path d="M8.5 5l7 7-7 7" />
      </NavButton>
      <NavButton label="Last move" disabled={atEnd} onClick={() => onSelect(totalPlies)}>
        <path d="M6.5 5l7 7-7 7" />
        <path d="M17.5 5v14" />
      </NavButton>
    </div>
  );
}

function NavButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="flex-1 flex items-center justify-center py-3 rounded-lg bg-[#3d3b38] text-[#e8e8e8] transition-colors enabled:hover:bg-[#4a4844] disabled:opacity-40 disabled:cursor-not-allowed"
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="w-6 h-6"
      >
        {children}
      </svg>
    </button>
  );
}
