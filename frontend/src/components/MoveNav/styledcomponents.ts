import styled from "styled-components";

export const Nav = styled.div`
  display: flex;
  flex-shrink: 0;
  gap: 0.5rem;
  border: 1px solid #403e3b;
  border-radius: 0.75rem;
  background: #302e2b;
  padding: 0.5rem;
`;

export const NavButtonElement = styled.button`
  display: flex;
  flex: 1 1 0%;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  background: #3d3b38;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  color: #e8e8e8;
  transition: background-color 150ms cubic-bezier(0.4, 0, 0.2, 1);

  &:enabled:hover {
    background: #4a4844;
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.4;
  }
`;

export const NavIcon = styled.svg`
  width: 1.5rem;
  height: 1.5rem;
`;
