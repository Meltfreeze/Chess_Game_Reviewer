import styled, { keyframes } from "styled-components";

const badgePop = keyframes`
  from {
    opacity: 0;
    transform: scale(0.6);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
`;

export const PieceImage = styled.img<{ $size: number; $fading: boolean }>`
  width: ${({ $size }) => $size}px;
  height: ${({ $size }) => $size}px;
  opacity: ${({ $fading }) => ($fading ? 0 : 1)};
  transition: opacity 180ms ease-out;
`;

export const BoardFrame = styled.div<{ $width: number }>`
  position: relative;
  width: ${({ $width }) => $width}px;
`;

export const Badge = styled.div<{ $top: number; $left: number }>`
  position: absolute;
  top: ${({ $top }) => $top}px;
  left: ${({ $left }) => $left}px;
  z-index: 10;
  width: 28px;
  height: 28px;
  animation: ${badgePop} 0.16s ease-out 0.14s backwards;
  pointer-events: none;
`;

export const BadgeIcon = styled.img`
  width: 1.75rem;
  height: 1.75rem;
  filter: drop-shadow(0 4px 3px rgb(0 0 0 / 0.07))
    drop-shadow(0 2px 2px rgb(0 0 0 / 0.06));
`;
