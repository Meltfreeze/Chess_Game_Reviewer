import type { MoveData } from "../types";
import { iconUrl } from "../api/client";

interface MoveListProps {
  moves: MoveData[];
  currentPly: number;
  onSelect: (ply: number) => void;
}

export default function MoveList({ moves, currentPly, onSelect }: MoveListProps) {
  const rows: { num: number; white?: MoveData; black?: MoveData }[] = [];
  for (let i = 0; i < moves.length; i += 2) {
    rows.push({
      num: moves[i].move_number,
      white: moves[i],
      black: moves[i + 1],
    });
  }

  return (
    <div className="text-base">
      <table className="w-full border-collapse">
        <tbody>
          {rows.map(({ num, white, black }) => (
            <tr key={num}>
              <td className="text-[#8b8987] w-7 pr-1">{num}.</td>
              <MoveCell move={white} ply={white!.ply + 1} currentPly={currentPly} onSelect={onSelect} />
              <MoveCell move={black} ply={black ? black.ply + 1 : -1} currentPly={currentPly} onSelect={onSelect} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MoveCell({
  move,
  ply,
  currentPly,
  onSelect,
}: {
  move?: MoveData;
  ply: number;
  currentPly: number;
  onSelect: (ply: number) => void;
}) {
  if (!move) return <td className="p-0.5" />;

  const active = ply === currentPly;
  return (
    <td className="p-0.5">
      <button
        type="button"
        onClick={() => onSelect(ply)}
        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded w-full text-left hover:bg-[#4a4844] ${
          active ? "bg-[#4a4844]" : ""
        }`}
      >
        <span>{move.san}</span>
        <img src={iconUrl(move.classification)} alt={move.classification} className="w-5 h-5" />
      </button>
    </td>
  );
}
