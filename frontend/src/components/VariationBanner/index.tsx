import { Banner, Message, ReturnButton } from "./styledcomponents";

interface VariationBannerProps {
  onReturn: () => void;
}

export default function VariationBanner({ onReturn }: VariationBannerProps) {
  return (
    <Banner>
      <Message>Exploring a variation</Message>
      <ReturnButton type="button" onClick={onReturn}>
        Back to the game
      </ReturnButton>
    </Banner>
  );
}
