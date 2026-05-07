import axios from "axios";
import { create } from "zustand";
import type { Incident } from "../api/types";
import { getIncidents, getIncident } from "../api/endpoints";

// Zustand store for incident data. Two slots:
// - `incidents[]` — list used by the Overview feed and any filtered views
// - `current` — single incident loaded for the IncidentDetail page
interface IncidentState {
  incidents: Incident[];
  current: Incident | null;
  loading: boolean;
  fetchIncidents: (params?: { status?: string; severity?: string }) => Promise<void>;
  fetchIncident: (id: number) => Promise<void>;
  updateIncident: (incident: Incident) => void;
}

export const useIncidentStore = create<IncidentState>((set) => ({
  incidents: [],
  current: null,
  loading: false,

  fetchIncidents: async (params, signal) => {
    set({ loading: true });
    try {
      const data = await getIncidents(params, signal);
      set({ incidents: data });
    } catch (e) {
      if (!axios.isCancel(e)) throw e;
    } finally {
      set({ loading: false });
    }
  },

  fetchIncident: async (id, signal) => {
    set({ loading: true });
    try {
      const data = await getIncident(id, signal);
      set({ current: data });
    } catch (e) {
      if (!axios.isCancel(e)) throw e;
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
