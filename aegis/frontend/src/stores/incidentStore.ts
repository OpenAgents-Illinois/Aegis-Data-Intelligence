import { create } from "zustand";
import type { Incident } from "../api/types";
import { getIncidents, getIncident } from "../api/endpoints";

interface IncidentState {
  incidents: Incident[];
  current: Incident | null;
  loading: boolean;
  fetchIncidents: (params?: { status?: string; severity?: string }) => Promise<void>;
  fetchIncident: (id: number) => Promise<void>;
  updateIncident: (incident: Incident) => void;
}

export const useIncidentStore = create<IncidentState>((set, get) => ({
  incidents: [],
  current: null,
  loading: false,

  fetchIncidents: async (params) => {
    set({ loading: true });
    try {
      const data = await getIncidents(params);
      set({ incidents: data });
    } finally {
      set({ loading: false });
    }
  },

  fetchIncident: async (id) => {
    set({ loading: true });
    try {
      const data = await getIncident(id);
      set({ current: data });
    } finally {
      set({ loading: false });
    }
  },

  updateIncident: (incident) => {
    set((state) => ({
      incidents: state.incidents.map((i) =>
        i.id === incident.id ? incident : i
      ),
      current: state.current?.id === incident.id ? incident : state.current,
    }));
  },
}));
