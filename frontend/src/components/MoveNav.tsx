import type { ReactNode } from "react";

interface MoveNavProps {
  flipped: boolean;
  canPrev: boolean;
  canNext: boolean;
  canJumpEnd: boolean;
  onFlip: () => void;
  onFirst: () => void;
  onPrev: () => void;
  onNext: () => void;
  onLast: () => void;
}

export default function MoveNav({
  flipped,
  canPrev,
  canNext,
  canJumpEnd,
  onFlip,
  onFirst,
  onPrev,
  onNext,
  onLast,
}: MoveNavProps) {
  return (
    <div className="shrink-0 bg-panel border border-panelBorder rounded-xl p-2 flex gap-2">
      <NavButton label="Flip board" disabled={false} pressed={flipped} onClick={onFlip}>
        <path d="M7 18V7a4 4 0 0 1 4-4h5" />
        <path d="m4 9 3-3 3 3" />
        <path d="M17 6v11a4 4 0 0 1-4 4H8" />
        <path d="m20 15-3 3-3-3" />
      </NavButton>
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
  pressed,
  onClick,
  children,
}: {
  label: string;
  disabled: boolean;
  pressed?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={pressed}
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
