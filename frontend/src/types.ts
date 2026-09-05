export type Classification =
  | "Brilliant"
  | "Great"
  | "Best"
  | "Excellent"
  | "Good"
  | "Book"
  | "Inaccuracy"
  | "Miss"
  | "Mistake"
  | "Blunder";

export interface MoveFacts {
  played: string;
  class: string;
  eval_before: number;
  eval_after: number;
  is_capture?: boolean;
  is_check?: boolean;
  is_castle?: boolean;
  best?: string | null;
  hanging?: string[];
  refutation?: string | null;
  missed_capture?: string;
  phase?: string;
  opening?: string | null;
}

export interface MoveData {
  ply: number;
  move_number: number;
  turn: "White" | "Black";
  san: string;
  uci: string;
  fen: string;
  fen_before: string;
  eval: string;
  eval_cp_white: number;
  classification: Classification;
  facts: MoveFacts;
  prompt_str: string;
  cp_loss: number;
  best_line: string[];
  best_uci: string | null;
  eval_swing: number;
  phase: string;
}

export interface PlayerStats {
  rating: number;
  acpl: number;
  accuracy: number;
}

export interface GameMeta {
  White: string;
  Black: string;
  WhiteElo: string;
  BlackElo: string;
  Result: string;
  Opening?: string;
  ECO?: string;
}

export interface CriticalMoment {
  ply: number;
  san: string;
  classification: Classification;
  eval_swing: number;
}

export interface AnalysisResult {
  move_data: MoveData[];
  stats: { White: PlayerStats; Black: PlayerStats };
  meta: GameMeta;
  hist: number[];
  critical_moments: CriticalMoment[];
  coach: { summary: string; comments: string[] };
  player_color: string;
}

export interface MoveReviewResult {
  move: MoveData;
  comment: string;
}

export interface EngineLine {
  eval: string;
  eval_cp_white: number;
  first_uci: string | null;
  san_line: string[];
}

export interface HealthInfo {
  ready: boolean;
  engine_path?: string;
  version?: string;
  gemini_configured?: boolean;
  default_depth?: number;
  error?: string;
}
