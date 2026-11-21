import { useEffect, useRef, useState } from "react";
import { authenticate, AuthError } from "../../api/auth";
import {
  Actions,
  CancelButton,
  Description,
  ErrorMessage,
  ModalForm,
  Overlay,
  PasswordInput,
  SubmitButton,
  Title,
} from "./styledcomponents";

interface PasswordModalProps {
  /** Called after a successful authentication, to resume the gated action. */
  onSuccess: () => void;
  onCancel: () => void;
}

/**
 * Blocking password prompt for the shared-secret gate. Shown when a gated
 * action (analysing a game) is attempted without a valid session token.
 */
export default function PasswordModal({ onSuccess, onCancel }: PasswordModalProps) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting || !password) return;
    setSubmitting(true);
    setError(null);
    try {
      await authenticate(password);
      onSuccess();
    } catch (err) {
      setError(err instanceof AuthError ? err.message : "Authentication failed");
      setPassword("");
      inputRef.current?.focus();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Overlay
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-title"
      onMouseDown={(e) => e.target === e.currentTarget && onCancel()}
    >
      <ModalForm onSubmit={submit}>
        <Title id="auth-title">
          Password required
        </Title>
        <Description>
          Enter the access password to analyze a game.
        </Description>

        <PasswordInput
          ref={inputRef}
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          placeholder="Password"
        />

        {error && <ErrorMessage>{error}</ErrorMessage>}

        <Actions>
          <CancelButton
            type="button"
            onClick={onCancel}
          >
            Cancel
          </CancelButton>
          <SubmitButton
            type="submit"
            disabled={submitting || !password}
          >
            {submitting ? "Checking…" : "Unlock"}
          </SubmitButton>
        </Actions>
      </ModalForm>
    </Overlay>
  );
}
