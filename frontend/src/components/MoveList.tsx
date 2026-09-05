import { Fragment } from "react";
import { iconUrl } from "../api/client";
import {
  isAncestorOf,
  mainLineIds,
  variationChildren,
  type MoveNode,
  type MoveTree,
} from "../moveTree";

interface MoveListProps {
  tree: MoveTree;
  onSelect: (nodeId: string) => void;
}

type Row =
  | { kind: "moves"; key: string; num: number; white?: MoveNode; black?: MoveNode }
  | { kind: "vars"; key: string; ids: string[] };

/**
 * Reviewed game in two columns, with variations nested underneath the
 * move they deviate from. Clicking any move — main line or variation — jumps
 * straight to it.
 */
export default function MoveList({ tree, onSelect }: MoveListProps) {
  const rows: Row[] = [];
  let pending: { num: number; white?: MoveNode; black?: MoveNode } | null = null;

  const flush = () => {
    if (!pending) return;
    const anchor = pending.white ?? pending.black;
    rows.push({ kind: "moves", key: `r${anchor!.id}`, ...pending });
    pending = null;
  };

  for (const id of mainLineIds(tree)) {
    const node = tree.nodes[id];

    if (node.parentId !== null) {
      if (node.turn === "White") {
        flush();
        pending = { num: node.moveNumber, white: node };
      } else if (pending && !pending.black) {
        pending.black = node;
      } else {
        flush();
        pending = { num: node.moveNumber, black: node };
      }
    }

    const vars = variationChildren(tree, id);
    if (vars.length > 0) {
      flush();
      rows.push({ kind: "vars", key: `v${id}`, ids: vars });
    }
  }
  flush();

  return (
    <div className="text-base">
      <table className="w-full border-collapse">
        <tbody>
          {rows.map((row) =>
            row.kind === "moves" ? (
              <tr key={row.key}>
                <td className="text-[#8b8987] w-7 pr-1 align-top">{row.num}.</td>
                <MoveCell node={row.white} tree={tree} onSelect={onSelect} />
                <MoveCell node={row.black} tree={tree} onSelect={onSelect} ellipsis={!row.white} />
              </tr>
            ) : (
              <tr key={row.key}>
                <td colSpan={3} className="pb-1">
                  {row.ids.map((id) => (
                    <Variation key={id} tree={tree} startId={id} depth={0} onSelect={onSelect} />
                  ))}
                </td>
              </tr>
            )
          )}
        </tbody>
      </table>
    </div>
  );
}

function MoveCell({
  node,
  tree,
  onSelect,
  ellipsis = false,
}: {
  node?: MoveNode;
  tree: MoveTree;
  onSelect: (nodeId: string) => void;
  ellipsis?: boolean;
}) {
  if (!node) return <td className="p-0.5" />;
  return (
    <td className="p-0.5">
      <button
        type="button"
        onClick={() => onSelect(node.id)}
        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded w-full text-left hover:bg-[#4a4844] ${
          node.id === tree.currentId ? "bg-[#4a4844]" : ""
        }`}
      >
        {ellipsis && <span className="text-[#8b8987]">…</span>}
        <span>{node.san}</span>
        <MoveMark node={node} />
      </button>
    </td>
  );
}

/**
 * One variation line. The chain follows the first child at each step; any extra
 * children are rendered as further-indented sub-variations underneath.
 */
function Variation({
  tree,
  startId,
  depth,
  onSelect,
}: {
  tree: MoveTree;
  startId: string;
  depth: number;
  onSelect: (nodeId: string) => void;
}) {
  const chain: MoveNode[] = [];
  let id: string | null = startId;
  while (id && tree.nodes[id]) {
    const node: MoveNode = tree.nodes[id];
    chain.push(node);
    id = node.childIds[0] ?? null;
  }

  const subIds = chain.flatMap((node) => node.childIds.slice(1));
  const active = isAncestorOf(tree, startId, tree.currentId);

  return (
    <div style={{ marginLeft: depth * 10 }}>
      <div
        className={`flex flex-wrap items-center gap-x-1 pl-2 border-l-2 text-sm ${
          active ? "border-accent" : "border-panelBorder"
        }`}
      >
        {chain.map((node, i) => (
          <Fragment key={node.id}>
            {(node.turn === "White" || i === 0) && (
              <span className={active ? "text-[#8b8987]" : "text-[#6b6967]"}>
                {node.moveNumber}
                {node.turn === "White" ? "." : "…"}
              </span>
            )}
            <button
              type="button"
              onClick={() => onSelect(node.id)}
              className={`inline-flex items-center gap-1 px-1 py-0.5 rounded hover:bg-[#4a4844] ${
                node.id === tree.currentId
                  ? "bg-[#4a4844] text-white"
                  : active
                    ? "text-[#d6d4d1]"
                    : "text-[#8b8987]"
              }`}
            >
              <span>{node.san}</span>
              <MoveMark node={node} />
            </button>
          </Fragment>
        ))}
      </div>
      {subIds.map((subId) => (
        <Variation
          key={subId}
          tree={tree}
          startId={subId}
          depth={depth + 1}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

function MoveMark({ node }: { node: MoveNode }) {
  if (node.data) {
    return (
      <img
        src={iconUrl(node.data.classification)}
        alt={node.data.classification}
        className="w-5 h-5"
      />
    );
  }
  if (node.status === "pending") {
    return (
      <span
        aria-label="Reviewing"
        title="Reviewing…"
        className="w-3.5 h-3.5 rounded-full border-2 border-[#8b8987] border-t-transparent animate-spin"
      />
    );
  }
  return (
    <span aria-label="Review failed" title={node.error ?? "Review failed"} className="text-red-400">
      !
    </span>
  );
}
