import axios from "axios";
import { create } from "zustand";
import type { LineageGraph } from "../api/types";
import { getLineageGraph } from "../api/endpoints";

interface LineageState {
  graph: LineageGraph | null;
  loading: boolean;
  fetchGraph: (connectionId?: number, signal?: AbortSignal) => Promise<void>;
}

export const useLineageStore = create<LineageState>((set) => ({
  graph: null,
  loading: false,

  fetchGraph: async (connectionId, signal) => {
    set({ loading: true });
    try {
      const params = connectionId ? { connection_id: connectionId } : undefined;
      const data = await getLineageGraph(params, signal);
      set({ graph: data });
    } catch (e) {
      if (!axios.isCancel(e)) throw e;
    } finally {
      set({ loading: false });
    }
  },
}));
