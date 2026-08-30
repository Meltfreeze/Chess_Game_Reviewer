import type { Classification } from "./types";

export const BADGE_COLORS: Record<string, string> = {
  Brilliant: "#1BADA6",
  Great: "#5C8BB0",
  Best: "#95BB4A",
  Excellent: "#95BB4A",
  Good: "#96AF8B",
  Book: "#A88865",
  Inaccuracy: "#F0C15C",
  Miss: "#EE6B55",
  Mistake: "#E58F2A",
  Blunder: "#CA3431",
};

/** Row order for the game summary panel — best moves first, worst last. */
export const SUMMARY_ORDER: Classification[] = [
  "Brilliant",
  "Great",
  "Book",
  "Best",
  "Excellent",
  "Good",
  "Inaccuracy",
  "Mistake",
  "Miss",
  "Blunder",
];
