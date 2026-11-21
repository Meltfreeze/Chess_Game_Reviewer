import styled from "styled-components";

export const Overlay = styled.div`
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgb(0 0 0 / 0.6);
  padding: 1rem;
`;

export const ModalForm = styled.form`
  width: 100%;
  max-width: 24rem;
  border: 1px solid #403e3b;
  border-radius: 0.75rem;
  background: #302e2b;
  padding: 1.25rem;
  box-shadow: 0 25px 50px -12px rgb(0 0 0 / 0.25);
`;

export const Title = styled.h2`
  margin-bottom: 0.25rem;
  font-size: 1.125rem;
  line-height: 1.75rem;
  font-weight: 700;
`;

export const Description = styled.p`
  margin-bottom: 1rem;
  color: #9ca3af;
  font-size: 0.875rem;
  line-height: 1.25rem;
`;

export const PasswordInput = styled.input`
  margin-bottom: 0.75rem;
  width: 100%;
  border: 1px solid #403e3b;
  border-radius: 0.5rem;
  background: #21201d;
  padding: 0.625rem;
  font-size: 0.875rem;
  line-height: 1.25rem;
`;

export const ErrorMessage = styled.p`
  margin-bottom: 0.75rem;
  color: #f87171;
  font-size: 0.875rem;
  line-height: 1.25rem;
`;

export const Actions = styled.div`
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
`;

export const CancelButton = styled.button`
  border-radius: 0.5rem;
  padding: 0.5rem 1rem;
  color: #d1d5db;
  font-size: 0.875rem;
  line-height: 1.25rem;

  &:hover {
    color: #ffffff;
  }
`;

export const SubmitButton = styled.button`
  border-radius: 0.5rem;
  background: #15803d;
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  line-height: 1.25rem;
  font-weight: 700;

  &:hover {
    background: #16a34a;
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.4;
  }
`;
