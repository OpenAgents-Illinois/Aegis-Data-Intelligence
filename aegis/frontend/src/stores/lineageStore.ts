import { create } from "zustand";
import type { LineageGraph } from "../api/types";
import { getLineageGraph } from "../api/endpoints";

interface LineageState {
  graph: LineageGraph | null;
  loading: boolean;
  fetchGraph: () => Promise<void>;
}

export const useLineageStore = create<LineageState>((set) => ({
  graph: null,
  loading: false,

  fetchGraph: async () => {
    set({ loading: true });
    try {
      const data = await getLineageGraph();
      set({ graph: data });
    } finally {
      set({ loading: false });
    }
  },
}));
