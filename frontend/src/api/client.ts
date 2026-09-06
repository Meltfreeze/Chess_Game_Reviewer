import type { AnalysisResult, HealthInfo, MoveReviewResult } from "../types";
import { authHeader, AuthError, clearToken } from "./auth";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export async function fetchHealth(): Promise<HealthInfo> {
  const res = await fetch(`${API_BASE}/api/health`);
  return res.json();
}

export function iconUrl(classification: string): string {
  return `${API_BASE}/api/icons/${classification}`;
}

export function cpToWinPercent(cp: number): number {
  const clamped = Math.max(-10000, Math.min(10000, cp));
  return 1 / (1 + 10 ** (-clamped / 400));
}

export interface AnalyzeOptions {
  pgn: string;
  playerColor: "White" | "Black";
  depth?: number;
  onProgress?: (ply: number, total: number) => void;
}

export interface ReviewMoveOptions {
  /** Position the move is played from. */
  fen: string;
  uci: string;
  /** Zero-based ply index of the move being played. */
  ply: number;
  /** UCI path from the starting position up to (not including) the move. */
  history: string[];
  depth?: number;
}

/** Review one move played off the reviewed game — see POST /api/move-review. */
export async function reviewMove(options: ReviewMoveOptions): Promise<MoveReviewResult> {
  const { fen, uci, ply, history, depth = 14 } = options;

  const res = await fetch(`${API_BASE}/api/move-review`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
    body: JSON.stringify({ fen, uci, ply, history, depth }),
  });

  if (res.status === 401) {
    clearToken();
    throw new AuthError();
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : "Move review failed");
  }

  return res.json();
}

export async function analyzeGame(options: AnalyzeOptions): Promise<AnalysisResult> {
  const { pgn, playerColor, depth = 14, onProgress } = options;

  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
    body: JSON.stringify({ pgn, player_color: playerColor, depth }),
  });

  if (res.status === 401) {
    clearToken();
    throw new AuthError();
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : "Analysis failed");
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response stream");

  const decoder = new TextDecoder();
  let buffer = "";
  let result: AnalysisResult | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      if (!part.trim()) continue;
      const lines = part.split("\n");
      let eventType = "message";
      let dataStr = "";
      for (const line of lines) {
        if (line.startsWith("event: ")) eventType = line.slice(7);
        if (line.startsWith("data: ")) dataStr = line.slice(6);
      }
      if (!dataStr) continue;
      const data = JSON.parse(dataStr);
      if (eventType === "progress") {
        onProgress?.(data.ply, data.total);
      } else if (eventType === "complete") {
        result = data as AnalysisResult;
      } else if (eventType === "error") {
        throw new Error(data.message || "Analysis error");
      }
    }
  }

  if (!result) throw new Error("Analysis completed without result");
  return result;
}
