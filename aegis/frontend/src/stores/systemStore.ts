import { create } from "zustand";
import type { Stats } from "../api/types";
import { getStats } from "../api/endpoints";

interface SystemState {
  stats: Stats | null;
  loading: boolean;
  fetchStats: () => Promise<void>;
}

export const useSystemStore = create<SystemState>((set) => ({
  stats: null,
  loading: false,

  fetchStats: async () => {
    set({ loading: true });
    try {
      const data = await getStats();
      set({ stats: data });
    } finally {
      set({ loading: false });
    }
  },
}));
