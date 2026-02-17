import { useCallback, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { LineageGraph as LineageGraphType } from "../api/types";

interface Props {
  graph: LineageGraphType;
  highlightTable?: string;
  onNodeClick?: (tableId: string) => void;
}

export default function LineageGraph({
  graph,
  highlightTable,
  onNodeClick,
}: Props) {
  const { initialNodes, initialEdges } = useMemo(() => {
    // Simple auto-layout: arrange nodes in columns by depth
    const inDegree = new Map<string, number>();
    graph.nodes.forEach((n) => inDegree.set(n.id, 0));
    graph.edges.forEach((e) => {
      inDegree.set(e.target, (inDegree.get(e.target) || 0) + 1);
    });

    // BFS for layering
    const layers = new Map<string, number>();
    const queue = graph.nodes
      .filter((n) => (inDegree.get(n.id) || 0) === 0)
      .map((n) => n.id);
    queue.forEach((id) => layers.set(id, 0));

    let head = 0;
    while (head < queue.length) {
      const current = queue[head++];
      const currentLayer = layers.get(current) || 0;
      graph.edges
        .filter((e) => e.source === current)
        .forEach((e) => {
          if (!layers.has(e.target)) {
            layers.set(e.target, currentLayer + 1);
            queue.push(e.target);
          }
        });
    }

    // Position nodes
    const layerCounts = new Map<number, number>();
    const initialNodes: Node[] = graph.nodes.map((n) => {
      const layer = layers.get(n.id) || 0;
      const idx = layerCounts.get(layer) || 0;
      layerCounts.set(layer, idx + 1);

      const isHighlighted = n.id === highlightTable;

      return {
        id: n.id,
        position: { x: layer * 280, y: idx * 80 },
        data: { label: n.label },
        style: {
          background: isHighlighted ? "#fef2f2" : "#ffffff",
          color: isHighlighted ? "#991b1b" : "#1f2937",
          border: `1px solid ${isHighlighted ? "#fca5a5" : "#d1d5db"}`,
          borderRadius: 8,
          padding: "8px 16px",
          fontSize: 12,
          fontWeight: 500,
          boxShadow: "0 1px 2px 0 rgb(0 0 0 / 0.05)",
        },
      };
    });

    const initialEdges: Edge[] = graph.edges.map((e, i) => ({
      id: `e-${i}`,
      source: e.source,
      target: e.target,
      animated: e.confidence < 1,
      style: {
        stroke: e.confidence >= 0.8 ? "#9ca3af" : "#d1d5db",
        strokeWidth: e.confidence >= 0.8 ? 2 : 1,
      },
    }));

    return { initialNodes, initialEdges };
  }, [graph, highlightTable]);

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeClick?.(node.id);
    },
    [onNodeClick]
  );

  return (
    <div className="w-full h-full" style={{ minHeight: 500 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#e5e7eb" gap={20} />
        <Controls
          style={{ background: "#ffffff", borderColor: "#e5e7eb" }}
        />
        <MiniMap
          nodeColor="#d1d5db"
          maskColor="rgba(255,255,255,0.7)"
          style={{ background: "#f9fafb" }}
        />
      </ReactFlow>
    </div>
  );
}
