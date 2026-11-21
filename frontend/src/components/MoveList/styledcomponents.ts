import styled, { keyframes } from "styled-components";

const spin = keyframes`
  to { transform: rotate(360deg); }
`;

export const List = styled.div`
  font-size: 1rem;
  line-height: 1.5rem;
`;

export const MovesTable = styled.table`
  width: 100%;
  border-collapse: collapse;
`;

export const MoveNumberCell = styled.td`
  width: 1.75rem;
  padding-right: 0.25rem;
  color: #8b8987;
  vertical-align: top;
`;

export const VariationCell = styled.td`
  padding-bottom: 0.25rem;
`;

export const MoveCellElement = styled.td`
  padding: 0.125rem;
`;

export const MoveButton = styled.button<{ $selected: boolean }>`
  display: inline-flex;
  width: 100%;
  align-items: center;
  gap: 0.25rem;
  border-radius: 0.25rem;
  background: ${({ $selected }) => ($selected ? "#4a4844" : "transparent")};
  padding: 0.125rem 0.375rem;
  text-align: left;

  &:hover {
    background: #4a4844;
  }
`;

export const Ellipsis = styled.span`
  color: #8b8987;
`;

export const VariationBlock = styled.div<{ $depth: number }>`
  margin-left: ${({ $depth }) => $depth * 10}px;
`;

export const VariationLine = styled.div<{ $active: boolean }>`
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  column-gap: 0.25rem;
  border-left: 2px solid ${({ $active }) => ($active ? "#e58f2a" : "#403e3b")};
  padding-left: 0.5rem;
  font-size: 0.875rem;
  line-height: 1.25rem;
`;

export const VariationNumber = styled.span<{ $active: boolean }>`
  color: ${({ $active }) => ($active ? "#8b8987" : "#6b6967")};
`;

export const VariationButton = styled.button<{
  $active: boolean;
  $selected: boolean;
}>`
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  border-radius: 0.25rem;
  background: ${({ $selected }) => ($selected ? "#4a4844" : "transparent")};
  padding: 0.125rem 0.25rem;
  color: ${({ $selected, $active }) =>
    $selected ? "#ffffff" : $active ? "#d6d4d1" : "#8b8987"};

  &:hover {
    background: #4a4844;
  }
`;

export const MoveIcon = styled.img`
  width: 1.25rem;
  height: 1.25rem;
`;

export const PendingMark = styled.span`
  width: 0.875rem;
  height: 0.875rem;
  border: 2px solid #8b8987;
  border-top-color: transparent;
  border-radius: 9999px;
  animation: ${spin} 1s linear infinite;
`;

export const ErrorMark = styled.span`
  color: #f87171;
`;
