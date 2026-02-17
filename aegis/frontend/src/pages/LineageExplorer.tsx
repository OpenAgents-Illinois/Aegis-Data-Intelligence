import { useEffect, useState } from "react";
import { useLineageStore } from "../stores/lineageStore";
import LineageGraphComponent from "../components/LineageGraph";

export default function LineageExplorer() {
  const { graph, loading, fetchGraph } = useLineageStore();
  const [search, setSearch] = useState("");
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  const filteredHighlight = search.trim()
    ? graph?.nodes.find((n) =>
        n.label.toLowerCase().includes(search.toLowerCase())
      )?.id
    : undefined;

  if (loading) {
    return (
      <div className="text-gray-400 text-center py-20">
        Loading lineage graph...
      </div>
    );
  }

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="space-y-4">
        <h2 className="text-2xl font-semibold text-gray-900">Lineage Explorer</h2>
        <div className="text-gray-400 text-center py-20 bg-white border border-gray-200 rounded-lg">
          No lineage data yet. Add a warehouse connection and wait for the
          lineage refresh cycle.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 h-full">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-gray-900">Lineage Explorer</h2>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-500">
            {graph.nodes.length} tables, {graph.edges.length} edges
          </span>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search tables..."
            className="bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 w-64 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
      </div>

      <div className="flex gap-4" style={{ height: "calc(100vh - 200px)" }}>
        {/* Graph */}
        <div className="flex-1 bg-white border border-gray-200 rounded-lg overflow-hidden">
          <LineageGraphComponent
            graph={graph}
            highlightTable={filteredHighlight}
            onNodeClick={(id) => setSelectedNode(id)}
          />
        </div>

        {/* Side Panel */}
        {selectedNode && (
          <div className="w-80 bg-white border border-gray-200 rounded-lg p-5 space-y-4 overflow-auto">
            <h3 className="text-base font-semibold text-gray-900">{selectedNode}</h3>

            <div className="space-y-2">
              <p className="text-xs text-gray-500 uppercase tracking-wider font-medium">
                Upstream
              </p>
              {graph.edges
                .filter((e) => e.target === selectedNode)
                .map((e) => (
                  <button
                    key={e.source}
                    onClick={() => setSelectedNode(e.source)}
                    className="block text-sm text-blue-600 hover:text-blue-800"
                  >
                    {e.source}
                  </button>
                ))}
              {graph.edges.filter((e) => e.target === selectedNode).length ===
                0 && <p className="text-sm text-gray-400">None (root)</p>}
            </div>

            <div className="space-y-2">
              <p className="text-xs text-gray-500 uppercase tracking-wider font-medium">
                Downstream
              </p>
              {graph.edges
                .filter((e) => e.source === selectedNode)
                .map((e) => (
                  <button
                    key={e.target}
                    onClick={() => setSelectedNode(e.target)}
                    className="block text-sm text-blue-600 hover:text-blue-800"
                  >
                    {e.target}
                  </button>
                ))}
              {graph.edges.filter((e) => e.source === selectedNode).length ===
                0 && <p className="text-sm text-gray-400">None (leaf)</p>}
            </div>

            <button
              onClick={() => setSelectedNode(null)}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              Close panel
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
