interface VariationBannerProps {
  onReturn: () => void;
}

export default function VariationBanner({ onReturn }: VariationBannerProps) {
  return (
    <div className="shrink-0 flex items-center justify-between gap-3 px-3 py-2 rounded-lg bg-accent/15 border border-accent/50 text-sm">
      <span className="font-semibold text-accent">Exploring a variation</span>
      <button
        type="button"
        onClick={onReturn}
        className="font-semibold text-accent underline decoration-accent/50 hover:decoration-accent"
      >
        Back to the game
      </button>
    </div>
  );
}
