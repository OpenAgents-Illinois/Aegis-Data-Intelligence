import LineageGraphComponent from "./LineageGraph";
import type { LineageGraph } from "../api/types";

interface Props {
  sourceTable: string;
  affectedTables: string[];
}

/**
 * Mini lineage graph for incident detail — shows blast radius.
 */
export default function BlastRadiusGraph({
  sourceTable,
  affectedTables,
}: Props) {
  const nodes = [
    { id: sourceTable, label: sourceTable },
    ...affectedTables.map((t) => ({ id: t, label: t })),
  ];

  const edges = affectedTables.map((t) => ({
    source: sourceTable,
    target: t,
    relationship: "affected",
    confidence: 1,
  }));

  const graph: LineageGraph = { nodes, edges };

  return (
    <div className="h-64 rounded-lg border border-gray-700 overflow-hidden">
      <LineageGraphComponent
        graph={graph}
        highlightTable={sourceTable}
      />
    </div>
  );
}
