import axios from "axios";
import { create } from "zustand";
import type { MonitoredTable } from "../api/types";
import { getTables } from "../api/endpoints";

interface TableState {
  tables: MonitoredTable[];
  loading: boolean;
  fetchTables: (params?: { connection_id?: number }, signal?: AbortSignal) => Promise<void>;
}

export const useTableStore = create<TableState>((set) => ({
  tables: [],
  loading: false,

  fetchTables: async (params, signal) => {
    set({ loading: true });
    try {
      const data = await getTables(params, signal);
      set({ tables: data });
    } catch (e) {
      if (!axios.isCancel(e)) throw e;
    } finally {
      set({ loading: false });
    }
  },
}));
