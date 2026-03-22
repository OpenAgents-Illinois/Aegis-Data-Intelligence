import { vi, it, expect, beforeEach, describe } from "vitest";
import axios from "axios";
import { useIncidentStore } from "../incidentStore";

vi.mock("../../api/endpoints", () => ({
  getIncidents: vi.fn(),
  getIncident: vi.fn(),
}));

import { getIncidents, getIncident } from "../../api/endpoints";

describe("incidentStore", () => {
  beforeEach(() => {
    useIncidentStore.setState({ incidents: [], current: null, loading: false });
    vi.clearAllMocks();
  });

  it("forwards signal to getIncidents", async () => {
    vi.mocked(getIncidents).mockResolvedValue([]);
    const controller = new AbortController();
    await useIncidentStore.getState().fetchIncidents(undefined, controller.signal);
    expect(vi.mocked(getIncidents)).toHaveBeenCalledWith(undefined, controller.signal);
  });

  it("forwards signal to getIncident", async () => {
    vi.mocked(getIncident).mockResolvedValue({ id: 1 } as any);
    const controller = new AbortController();
    await useIncidentStore.getState().fetchIncident(1, controller.signal);
    expect(vi.mocked(getIncident)).toHaveBeenCalledWith(1, controller.signal);
  });

  it("does not update state when getIncidents is aborted", async () => {
    vi.mocked(getIncidents).mockRejectedValue(new axios.CanceledError());
    const controller = new AbortController();
    controller.abort();
    await useIncidentStore.getState().fetchIncidents(undefined, controller.signal);
    expect(useIncidentStore.getState().incidents).toEqual([]);
    expect(useIncidentStore.getState().loading).toBe(false);
  });

  it("does not update state when getIncident is aborted", async () => {
    vi.mocked(getIncident).mockRejectedValue(new axios.CanceledError());
    const controller = new AbortController();
    controller.abort();
    await useIncidentStore.getState().fetchIncident(1, controller.signal);
    expect(useIncidentStore.getState().current).toBeNull();
    expect(useIncidentStore.getState().loading).toBe(false);
  });
});
