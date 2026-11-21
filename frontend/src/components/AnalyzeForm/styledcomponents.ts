import styled, { keyframes } from "styled-components";

const spin = keyframes`
  to { transform: rotate(360deg); }
`;

const colorTransition =
  "color 150ms cubic-bezier(0.4, 0, 0.2, 1), background-color 150ms cubic-bezier(0.4, 0, 0.2, 1), border-color 150ms cubic-bezier(0.4, 0, 0.2, 1)";

export const FormContainer = styled.div`
  margin-bottom: 1.5rem;
  border: 1px solid #403e3b;
  border-radius: 1rem;
  background: #302e2b;
  padding: 1.25rem;

  @media (min-width: 760px) {
    padding: 1.75rem;
  }
`;

export const Title = styled.h2`
  margin-bottom: 1.25rem;
  color: #f2f1ed;
  font-size: 1.25rem;
  line-height: 1.75rem;
  font-weight: 700;
`;

export const Layout = styled.div`
  display: grid;
  gap: 1.5rem;

  @media (min-width: 760px) {
    grid-template-columns: minmax(0, 1.55fr) minmax(280px, 1fr);
  }
`;

export const DropZone = styled.div<{ $dragging: boolean }>`
  overflow: hidden;
  border: 1px dashed ${({ $dragging }) => ($dragging ? "#e58f2a" : "#4a4742")};
  border-radius: 0.75rem;
  background: ${({ $dragging }) =>
    $dragging ? "rgb(229 143 42 / 0.05)" : "#21201d"};
  box-shadow: ${({ $dragging }) =>
    $dragging ? "0 0 0 2px rgb(229 143 42 / 0.3)" : "none"};
  transition: ${colorTransition};
`;

export const TextareaBox = styled.div`
  position: relative;
  min-height: 16rem;

  @media (min-width: 760px) {
    min-height: 18rem;
  }
`;

export const Placeholder = styled.pre`
  position: absolute;
  inset: 0;
  padding: 1.5rem;
  color: #756d61;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    "Courier New", monospace;
  font-size: 0.875rem;
  line-height: 2rem;
  white-space: pre-wrap;
  pointer-events: none;
`;

export const PgnInput = styled.textarea`
  position: absolute;
  inset: 0;
  z-index: 10;
  width: 100%;
  height: 100%;
  resize: none;
  background: transparent;
  padding: 1.5rem;
  color: #e8e6df;
  caret-color: #e58f2a;
  outline: 2px solid transparent;
  outline-offset: 2px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    "Courier New", monospace;
  font-size: 0.875rem;
  line-height: 2rem;

  &:focus {
    box-shadow: inset 0 0 0 2px rgb(229 143 42 / 0.5);
  }

  &:read-only {
    cursor: not-allowed;
    opacity: 0.75;
  }
`;

export const UploadRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  border-top: 1px solid #403e3b;
  padding: 0.75rem 1rem;
`;

export const UploadLabel = styled.label<{ $loading: boolean }>`
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  border: 1px solid #4a4742;
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
  color: #bdb7ae;
  font-size: 0.875rem;
  line-height: 1.25rem;
  font-weight: 500;
  cursor: ${({ $loading }) => ($loading ? "not-allowed" : "pointer")};
  opacity: ${({ $loading }) => ($loading ? 0.6 : 1)};
  transition: ${colorTransition};

  &:focus-within {
    box-shadow: 0 0 0 2px rgb(229 143 42 / 0.5);
  }

  ${({ $loading }) =>
    !$loading &&
    `
      &:hover {
        border-color: rgb(229 143 42 / 0.7);
        color: #eeeae3;
      }
    `}
`;

export const HiddenFileInput = styled.input`
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  margin: -1px;
  padding: 0;
  border-width: 0;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
`;

export const FormColumn = styled.div`
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 1.25rem;
`;

export const DepthCard = styled.div`
  border: 1px solid #403e3b;
  border-radius: 0.75rem;
  background: #292724;
  padding: 1.25rem;
`;

export const DepthHeading = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
`;

export const DepthLabel = styled.label`
  color: #bdb7ae;
  font-size: 0.875rem;
  line-height: 1.25rem;
  font-weight: 600;
`;

export const DepthOutput = styled.output`
  color: #e58f2a;
  font-size: 1.25rem;
  line-height: 1.75rem;
  font-weight: 600;
`;

export const DepthHint = styled.p`
  margin-top: 0.25rem;
  color: #756f67;
  font-size: 0.875rem;
  line-height: 1.25rem;
`;

export const DepthSlider = styled.input<{ $progress: number }>`
  margin-top: 1.75rem;
  width: 100%;
  height: 0.375rem;
  appearance: none;
  border-radius: 9999px;
  background: ${({ $progress }) =>
    `linear-gradient(to right, #e58f2a 0%, #e58f2a ${$progress}%, #56514b ${$progress}%, #56514b 100%)`};
  cursor: pointer;
  outline: 2px solid transparent;
  outline-offset: 2px;

  &:focus-visible {
    box-shadow: 0 0 0 4px #292724, 0 0 0 6px rgb(229 143 42 / 0.6);
  }

  &::-webkit-slider-thumb {
    width: 1.25rem;
    height: 1.25rem;
    appearance: none;
    border: 2px solid #292724;
    border-radius: 9999px;
    background: #e58f2a;
    box-shadow: 0 0 0 2px #e58f2a;
  }

  &::-moz-range-thumb {
    width: 1.25rem;
    height: 1.25rem;
    border: 2px solid #292724;
    border-radius: 9999px;
    background: #e58f2a;
  }
`;

export const DepthBands = styled.div`
  margin-top: 1rem;
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  line-height: 1rem;
  font-weight: 500;
`;

export const DepthBand = styled.span<{ $active: boolean }>`
  color: ${({ $active }) => ($active ? "#e58f2a" : "#756f67")};
  font-weight: ${({ $active }) => ($active ? 600 : 500)};
`;

export const SubmitButton = styled.button`
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  border-radius: 0.75rem;
  background: #e58f2a;
  padding: 0.875rem 1.5rem;
  color: #1c1400;
  font-weight: 700;
  transition: ${colorTransition};

  &:hover {
    background: #f0a444;
  }

  &:focus {
    outline: 2px solid transparent;
    outline-offset: 2px;
  }

  &:focus-visible {
    box-shadow: 0 0 0 2px #302e2b, 0 0 0 4px rgb(229 143 42 / 0.7);
  }

  &:disabled {
    cursor: not-allowed;
    background: #272522;
    color: #756f67;
  }

  &:disabled:hover {
    background: #272522;
  }
`;

export const EngineWarning = styled.p`
  margin-top: 0.5rem;
  color: #f87171;
  font-size: 0.875rem;
  line-height: 1.25rem;
`;

export const GeminiWarning = styled.p`
  margin-top: 0.5rem;
  color: #fbbf24;
  font-size: 0.875rem;
  line-height: 1.25rem;
`;

export const UploadSvg = styled.svg`
  width: 1rem;
  height: 1rem;
  fill: none;
  stroke: currentColor;
`;

export const PlaySvg = styled.svg`
  width: 1rem;
  height: 1rem;
  fill: currentColor;
`;

export const SpinnerMark = styled.span`
  width: 1rem;
  height: 1rem;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 9999px;
  animation: ${spin} 1s linear infinite;
`;
