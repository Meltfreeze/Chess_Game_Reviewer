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
  is_sacrifice?: boolean;
  best?: string | null;
  best_line?: string[];
  hanging?: string[];
  refutation?: string | null;
  forcing_line?: string[];
  missed_capture?: string;
  runner_up?: string;
  runner_up_hanging?: string[];
  runner_up_fails?: boolean;
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
  best_move: string | null;
  played_move: string;
  best_wp: number;
  second_best_wp: number;
  legal_move_count: number;
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
  commentary_succeeded?: boolean;
  commentary_status?: CommentaryStatus;
  all_comments_succeeded?: boolean;
}

export interface CommentaryStatus {
  gemini_attempted: boolean;
  generation_complete: boolean;
  summary_generated: boolean;
  summary_accepted: boolean;
  requested_comments: number;
  generated_comments: number;
  accepted_comments: number;
  fallback_used: boolean;
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

export interface AnalysisFailure {
  kind: "timeout" | "engine" | "unknown";
  pgn: string;
  depth: number;
}

export interface AnalysisCompletion {
  pgn: string;
  commentarySucceeded: boolean;
  commentaryStatus?: CommentaryStatus;
}
