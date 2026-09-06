import { useEffect, useRef, useState } from "react";
import { authenticate, AuthError } from "../api/auth";

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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-title"
      onMouseDown={(e) => e.target === e.currentTarget && onCancel()}
    >
      <form
        onSubmit={submit}
        className="w-full max-w-sm bg-panel border border-panelBorder rounded-xl p-5 shadow-2xl"
      >
        <h2 id="auth-title" className="text-lg font-bold mb-1">
          Password required
        </h2>
        <p className="text-sm text-gray-400 mb-4">
          Enter the access password to analyze a game.
        </p>

        <input
          ref={inputRef}
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          placeholder="Password"
          className="w-full bg-[#21201d] border border-panelBorder rounded-lg p-2.5 text-sm mb-3"
        />

        {error && <p className="text-red-400 text-sm mb-3">{error}</p>}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 rounded-lg text-sm text-gray-300 hover:text-white"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || !password}
            className="px-5 py-2 rounded-lg font-bold text-sm bg-green-700 hover:bg-green-600 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {submitting ? "Checking…" : "Unlock"}
          </button>
        </div>
      </form>
    </div>
  );
}
