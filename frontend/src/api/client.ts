import type { AnalysisResult, EngineLine, HealthInfo } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export async function fetchHealth(): Promise<HealthInfo> {
  const res = await fetch(`${API_BASE}/api/health`);
  return res.json();
}

export async function fetchPosition(
  fen: string,
  depth = 18,
  multipv = 3
): Promise<{ lines: EngineLine[] }> {
  const params = new URLSearchParams({ fen, depth: String(depth), multipv: String(multipv) });
  const res = await fetch(`${API_BASE}/api/position?${params}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Position analysis failed");
  }
  return res.json();
}

export function iconUrl(classification: string): string {
  return `${API_BASE}/api/icons/${classification}`;
}

export function accuracyFromAcpl(acpl: number): number {
  return Math.round(Math.max(10, Math.min(99, 100 * 0.98 ** acpl)));
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

export async function analyzeGame(options: AnalyzeOptions): Promise<AnalysisResult> {
  const { pgn, playerColor, depth = 18, onProgress } = options;

  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pgn, player_color: playerColor, depth }),
  });

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
