import { Fragment } from "react";
import { iconUrl } from "../../api/client";
import {
  isAncestorOf,
  mainLineIds,
  variationChildren,
  type MoveNode,
  type MoveTree,
} from "../../moveTree";
import {
  Ellipsis,
  ErrorMark,
  List,
  MoveButton,
  MoveCellElement,
  MoveIcon,
  MoveNumberCell,
  MovesTable,
  PendingMark,
  VariationBlock,
  VariationButton,
  VariationCell,
  VariationLine,
  VariationNumber,
} from "./styledcomponents";

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
    <List>
      <MovesTable>
        <tbody>
          {rows.map((row) =>
            row.kind === "moves" ? (
              <tr key={row.key}>
                <MoveNumberCell>{row.num}.</MoveNumberCell>
                <MoveCell node={row.white} tree={tree} onSelect={onSelect} />
                <MoveCell node={row.black} tree={tree} onSelect={onSelect} ellipsis={!row.white} />
              </tr>
            ) : (
              <tr key={row.key}>
                <VariationCell colSpan={3}>
                  {row.ids.map((id) => (
                    <Variation key={id} tree={tree} startId={id} depth={0} onSelect={onSelect} />
                  ))}
                </VariationCell>
              </tr>
            )
          )}
        </tbody>
      </MovesTable>
    </List>
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
  if (!node) return <MoveCellElement />;
  return (
    <MoveCellElement>
      <MoveButton
        type="button"
        onClick={() => onSelect(node.id)}
        $selected={node.id === tree.currentId}
      >
        {ellipsis && <Ellipsis>…</Ellipsis>}
        <span>{node.san}</span>
        <MoveMark node={node} />
      </MoveButton>
    </MoveCellElement>
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
    <VariationBlock $depth={depth}>
      <VariationLine $active={active}>
        {chain.map((node, i) => (
          <Fragment key={node.id}>
            {(node.turn === "White" || i === 0) && (
              <VariationNumber $active={active}>
                {node.moveNumber}
                {node.turn === "White" ? "." : "…"}
              </VariationNumber>
            )}
            <VariationButton
              type="button"
              onClick={() => onSelect(node.id)}
              $active={active}
              $selected={node.id === tree.currentId}
            >
              <span>{node.san}</span>
              <MoveMark node={node} />
            </VariationButton>
          </Fragment>
        ))}
      </VariationLine>
      {subIds.map((subId) => (
        <Variation
          key={subId}
          tree={tree}
          startId={subId}
          depth={depth + 1}
          onSelect={onSelect}
        />
      ))}
    </VariationBlock>
  );
}

function MoveMark({ node }: { node: MoveNode }) {
  if (node.data) {
    return (
      <MoveIcon
        src={iconUrl(node.data.classification)}
        alt={node.data.classification}
      />
    );
  }
  if (node.status === "pending") {
    return (
      <PendingMark
        aria-label="Reviewing"
        title="Reviewing…"
      />
    );
  }
  return (
    <ErrorMark aria-label="Review failed" title={node.error ?? "Review failed"}>
      !
    </ErrorMark>
  );
}
