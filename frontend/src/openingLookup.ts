export interface OpeningInfo {
  eco: string;
  name: string;
}

let openingsPromise: Promise<Map<string, OpeningInfo>> | null = null;

export async function lookupOpening(uciMoves: string[]): Promise<OpeningInfo | null> {
  const openings = await loadOpenings();
  return findOpening(openings, uciMoves);
}

export function findOpening(
  openings: Map<string, OpeningInfo>,
  uciMoves: string[]
): OpeningInfo | null {
  for (let end = uciMoves.length; end > 0; end -= 1) {
    const match = openings.get(uciMoves.slice(0, end).join(" "));
    if (match) return match;
  }
  return null;
}

function loadOpenings(): Promise<Map<string, OpeningInfo>> {
  if (!openingsPromise) {
    const url = `${import.meta.env.BASE_URL}data/openings.tsv`;
    openingsPromise = fetch(url)
      .then((response) => {
        if (!response.ok) throw new Error("Opening table could not be loaded");
        return response.text();
      })
      .then(parseOpeningTable);
  }
  return openingsPromise;
}

export function parseOpeningTable(tsv: string): Map<string, OpeningInfo> {
  const openings = new Map<string, OpeningInfo>();
  for (const line of tsv.split(/\r?\n/)) {
    if (!line || line.startsWith("#") || line.startsWith("uci\t")) continue;
    const [uci, eco, name] = line.split("\t");
    if (uci && eco && name) openings.set(uci, { eco, name });
  }
  return openings;
}
