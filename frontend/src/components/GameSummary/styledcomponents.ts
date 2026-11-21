import styled, { css } from "styled-components";

const rowGrid = css`
  display: grid;
  grid-template-columns: 1fr 6.5rem 2rem 6.5rem;
  align-items: center;
  column-gap: 0.5rem;
`;

export const Summary = styled.div`
  font-size: 1rem;
  line-height: 1.5rem;
`;

export const HeaderRow = styled.div`
  ${rowGrid};
  margin-bottom: 0.5rem;
  color: #8b8987;
  font-size: 0.875rem;
  line-height: 1.25rem;
  font-weight: 600;
`;

export const PlayerName = styled.span`
  overflow: hidden;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

export const AccuracyRow = styled.div`
  ${rowGrid};
  margin-bottom: 0.75rem;
`;

export const Score = styled.span<{ $dark?: boolean }>`
  display: block;
  border-radius: 0.25rem;
  background: ${({ $dark }) => ($dark ? "#262522" : "#f5f5f0")};
  padding: 0.375rem 0.5rem;
  color: ${({ $dark }) => ($dark ? "#e8e8e8" : "#262522")};
  text-align: center;
  font-weight: 700;
`;

export const Divider = styled.div`
  margin-bottom: 0.25rem;
  border-top: 1px solid #403e3b;
`;

export const ClassificationRow = styled.div`
  ${rowGrid};
  padding-top: 0.375rem;
  padding-bottom: 0.375rem;
`;

export const ClassificationLabel = styled.span<{ $color: string }>`
  color: ${({ $color }) => $color};
`;

export const ClassificationCount = styled.span<{ $color: string }>`
  color: ${({ $color }) => $color};
  text-align: center;
  font-weight: 600;
`;

export const ClassificationIcon = styled.img`
  width: 1.5rem;
  height: 1.5rem;
  justify-self: center;
`;

export const RatingRow = styled.div`
  ${rowGrid};
  border-top: 1px solid #403e3b;
  padding-top: 0.75rem;
  font-size: 1rem;
  line-height: 1.5rem;
`;

export const RatingLabel = styled.span`
  color: #b9b7b4;
  line-height: 1.25;
`;
