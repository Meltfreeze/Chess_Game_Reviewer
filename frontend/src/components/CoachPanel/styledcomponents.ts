import styled, { keyframes } from "styled-components";

const spin = keyframes`
  to { transform: rotate(360deg); }
`;

export const Panel = styled.div`
  border-radius: 1rem;
  background: #ffffff;
  padding: 1rem;
  color: #2b2b2b;
  line-height: 1.625;
  box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
`;

export const BadgeRow = styled.div`
  margin-bottom: 0.5rem;
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
`;

export const BadgeIcon = styled.img`
  width: 1.25rem;
  height: 1.25rem;
`;

export const Badge = styled.span<{ $color: string }>`
  border-radius: 9999px;
  background: ${({ $color }) => $color};
  padding: 0.125rem 0.625rem;
  color: #ffffff;
  font-size: 0.75rem;
  line-height: 1rem;
  font-weight: 800;
`;

export const LoadingMessage = styled.div`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #6b7280;
`;

export const LoadingSpinner = styled.span`
  width: 1rem;
  height: 1rem;
  border: 2px solid #9ca3af;
  border-top-color: transparent;
  border-radius: 9999px;
  animation: ${spin} 1s linear infinite;
`;

export const ErrorMessage = styled.div`
  color: #dc2626;
`;

export const BestLine = styled.div`
  margin-top: 0.75rem;
  border-top: 1px solid #e5e7eb;
  padding-top: 0.5rem;
  color: #4b5563;
  font-size: 0.875rem;
  line-height: 1.25rem;
`;

export const BestLineLabel = styled.span`
  font-weight: 600;
`;
