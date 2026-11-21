import styled from "styled-components";

export const Sidebar = styled.div`
  display: flex;
  height: 100%;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #403e3b;
  border-radius: 0.75rem;
  background: #302e2b;
`;

export const TopSection = styled.div`
  flex-shrink: 0;
  padding: 0.75rem 0.75rem 0;
`;

export const GraphSection = styled.div`
  margin-top: 0.75rem;
`;

export const Tabs = styled.div`
  display: flex;
  flex-shrink: 0;
  gap: 0.25rem;
  padding: 0.75rem 0.75rem 0;
`;

export const TabButtonElement = styled.button<{ $active: boolean }>`
  border-radius: 0.375rem;
  background: ${({ $active }) => ($active ? "#403e3b" : "transparent")};
  padding: 0.375rem 0.75rem;
  color: ${({ $active }) => ($active ? "#ffffff" : "#8b8987")};
  font-size: 1rem;
  line-height: 1.5rem;
  font-weight: 600;

  &:hover {
    color: ${({ $active }) => ($active ? "#ffffff" : "#e8e8e8")};
  }
`;

export const ScrollArea = styled.div`
  min-height: 0;
  flex: 1 1 0%;
  overflow-y: auto;
  padding: 0.75rem;
  scrollbar-color: #5c5a57 #302e2b;
  scrollbar-width: thin;
`;

export const Footer = styled.div`
  flex-shrink: 0;
  padding: 0 0.75rem 0.75rem;
`;
