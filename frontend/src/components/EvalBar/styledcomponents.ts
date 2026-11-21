import styled from "styled-components";

export const Bar = styled.div<{ $height: number }>`
  position: relative;
  width: 26px;
  height: ${({ $height }) => $height}px;
  overflow: hidden;
  border-radius: 0.25rem;
  background: #403e3b;
  box-shadow: inset 0 2px 4px 0 rgb(0 0 0 / 0.05);
`;

export const WhiteFill = styled.div<{ $height: number; $flipped: boolean }>`
  position: absolute;
  top: ${({ $flipped }) => ($flipped ? "0" : "auto")};
  bottom: ${({ $flipped }) => ($flipped ? "auto" : "0")};
  width: 100%;
  height: ${({ $height }) => $height}px;
  background: #f5f5f0;
  transition: height 0.25s ease;
`;

export const EvalLabel = styled.span<{
  $atBottom: boolean;
  $whiteAhead: boolean;
}>`
  position: absolute;
  top: ${({ $atBottom }) => ($atBottom ? "auto" : "3px")};
  bottom: ${({ $atBottom }) => ($atBottom ? "3px" : "auto")};
  left: 0;
  width: 100%;
  color: ${({ $whiteAhead }) => ($whiteAhead ? "#403e3b" : "#f5f5f0")};
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.03em;
  text-align: center;
  user-select: none;
  pointer-events: none;
`;
