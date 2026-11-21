import styled from "styled-components";

export const Banner = styled.div`
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  border: 1px solid rgb(229 143 42 / 0.5);
  border-radius: 0.5rem;
  background: rgb(229 143 42 / 0.15);
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  line-height: 1.25rem;
`;

export const Message = styled.span`
  color: #e58f2a;
  font-weight: 600;
`;

export const ReturnButton = styled.button`
  color: #e58f2a;
  font-weight: 600;
  text-decoration-line: underline;
  text-decoration-color: rgb(229 143 42 / 0.5);

  &:hover {
    text-decoration-color: #e58f2a;
  }
`;
