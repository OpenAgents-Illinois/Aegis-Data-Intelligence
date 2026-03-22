import { vi, it, expect, beforeEach, describe } from "vitest";
import axios from "axios";
import { useSystemStore } from "../systemStore";

vi.mock("../../api/endpoints", () => ({
  getStats: vi.fn(),
  getStatus: vi.fn(),
}));

import { getStats, getStatus } from "../../api/endpoints";

beforeEach(() => {
  useSystemStore.setState({ stats: null, llmEnabled: null, loading: false });
  vi.clearAllMocks();
});

describe("systemStore", () => {
  it("forwards signal to getStats", async () => {
    vi.mocked(getStats).mockResolvedValue({ health_score: 99, total_tables: 1, healthy_tables: 1, open_incidents: 0, critical_incidents: 0, anomalies_24h: 0, avg_resolution_time_minutes: null });
    const controller = new AbortController();
    await useSystemStore.getState().fetchStats(controller.signal);
    expect(getStats).toHaveBeenCalledWith(controller.signal);
  });

  it("does not update state when aborted", async () => {
    const cancelError = new axios.CanceledError();
    vi.mocked(getStats).mockRejectedValue(cancelError);
    const controller = new AbortController();
    controller.abort();
    await useSystemStore.getState().fetchStats(controller.signal);
    expect(useSystemStore.getState().stats).toBeNull();
    expect(useSystemStore.getState().loading).toBe(false);
  });

  it("leaves llmEnabled null when getStatus rejects with CanceledError", async () => {
    vi.mocked(getStatus).mockRejectedValue(new axios.CanceledError());
    const controller = new AbortController();
    controller.abort();
    await useSystemStore.getState().fetchStatus(controller.signal);
    expect(useSystemStore.getState().llmEnabled).toBeNull();
  });

  it("leaves llmEnabled null when getStatus rejects with a network error", async () => {
    vi.mocked(getStatus).mockRejectedValue(new Error("Network Error"));
    await useSystemStore.getState().fetchStatus();
    expect(useSystemStore.getState().llmEnabled).toBeNull();
  });
});
