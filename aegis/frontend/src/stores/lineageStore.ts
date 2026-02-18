import { create } from "zustand";
import type { LineageGraph } from "../api/types";
import { getLineageGraph } from "../api/endpoints";

interface LineageState {
  graph: LineageGraph | null;
  loading: boolean;
  fetchGraph: (connectionId?: number) => Promise<void>;
}

export const useLineageStore = create<LineageState>((set) => ({
  graph: null,
  loading: false,

  fetchGraph: async (connectionId) => {
    set({ loading: true });
    try {
      const params = connectionId ? { connection_id: connectionId } : undefined;
      const data = await getLineageGraph(params);
      set({ graph: data });
    } finally {
      set({ loading: false });
    }
  },
}));
