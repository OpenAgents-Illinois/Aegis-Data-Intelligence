import { create } from "zustand";
import type { MonitoredTable } from "../api/types";
import { getTables } from "../api/endpoints";

interface TableState {
  tables: MonitoredTable[];
  loading: boolean;
  fetchTables: (params?: { connection_id?: number }) => Promise<void>;
}

export const useTableStore = create<TableState>((set) => ({
  tables: [],
  loading: false,

  fetchTables: async (params) => {
    set({ loading: true });
    try {
      const data = await getTables(params);
      set({ tables: data });
    } finally {
      set({ loading: false });
    }
  },
}));
