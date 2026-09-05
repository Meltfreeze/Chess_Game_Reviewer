import type { ReactNode } from "react";

interface MoveNavProps {
  canPrev: boolean;
  canNext: boolean;
  canJumpEnd: boolean;
  onFirst: () => void;
  onPrev: () => void;
  onNext: () => void;
  onLast: () => void;
}

export default function MoveNav({
  canPrev,
  canNext,
  canJumpEnd,
  onFirst,
  onPrev,
  onNext,
  onLast,
}: MoveNavProps) {
  return (
    <div className="shrink-0 bg-panel border border-panelBorder rounded-xl p-2 flex gap-2">
      <NavButton label="First move" disabled={!canPrev} onClick={onFirst}>
        <path d="M6.5 5v14" />
        <path d="M17.5 5l-7 7 7 7" />
      </NavButton>
      <NavButton label="Previous move" disabled={!canPrev} onClick={onPrev}>
        <path d="M15.5 5l-7 7 7 7" />
      </NavButton>
      <NavButton label="Next move" disabled={!canNext} onClick={onNext}>
        <path d="M8.5 5l7 7-7 7" />
      </NavButton>
      <NavButton label="Last move" disabled={!canJumpEnd} onClick={onLast}>
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
