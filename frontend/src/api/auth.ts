/**
 * Client side of the shared-secret gate. This is purely a UX convenience —
 * holding a token so the password isn't re-typed, and knowing when to prompt.
 * It enforces nothing: every protected endpoint re-verifies the token on the
 * server, so tampering with anything here just yields a 401.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const STORAGE_KEY = "cgr_auth";
// Treat a token as expired slightly early so we prompt rather than fire a
// request that's about to be rejected mid-flight.
const EXPIRY_SKEW_MS = 30_000;

interface StoredAuth {
  token: string;
  expiresAt: number;
}

/** Thrown when a protected request comes back 401 (missing/expired/invalid token). */
export class AuthError extends Error {
  constructor(message = "Authentication required") {
    super(message);
    this.name = "AuthError";
  }
}

let cached: StoredAuth | null | undefined;

function read(): StoredAuth | null {
  if (cached !== undefined) return cached;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    cached = raw ? (JSON.parse(raw) as StoredAuth) : null;
  } catch {
    cached = null;
  }
  return cached;
}

export function hasValidToken(): boolean {
  const auth = read();
  return !!auth && auth.expiresAt - EXPIRY_SKEW_MS > Date.now();
}

export function authHeader(): Record<string, string> {
  const auth = read();
  return auth ? { Authorization: `Bearer ${auth.token}` } : {};
}

export function clearToken(): void {
  cached = null;
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable — in-memory clear is enough */
  }
}

/**
 * Exchange the shared password for a token. Throws AuthError on a wrong
 * password (401) or when the server has no secret configured (503), with the
 * server's message so the modal can show why.
 */
export async function authenticate(password: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/auth`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new AuthError(typeof body.detail === "string" ? body.detail : "Authentication failed");
  }

  const { token, expires_in } = await res.json();
  const stored: StoredAuth = { token, expiresAt: Date.now() + expires_in * 1000 };
  cached = stored;
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
  } catch {
    /* storage unavailable — the in-memory cache still carries the session */
  }
}
