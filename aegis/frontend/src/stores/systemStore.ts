import axios from "axios";
import { create } from "zustand";
import type { Stats } from "../api/types";
import { getStats, getStatus } from "../api/endpoints";

interface SystemState {
  stats: Stats | null;
  llmEnabled: boolean | null;
  loading: boolean;
  fetchStats: (signal?: AbortSignal) => Promise<void>;
  fetchStatus: (signal?: AbortSignal) => Promise<void>;
}

export const useSystemStore = create<SystemState>((set) => ({
  stats: null,
  llmEnabled: null,
  loading: false,

  fetchStats: async (signal) => {
    set({ loading: true });
    try {
      const data = await getStats(signal);
      set({ stats: data });
    } catch (e) {
      if (!axios.isCancel(e)) throw e;
    } finally {
      set({ loading: false });
    }
  },

  fetchStatus: async (signal) => {
    try {
      const data = await getStatus(signal);
      set({ llmEnabled: data.llm_enabled });
    } catch {
      // Non-fatal — includes CanceledError
    }
  },
}));
