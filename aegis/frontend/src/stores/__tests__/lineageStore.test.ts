import { vi, it, expect, beforeEach, describe } from "vitest";
import axios from "axios";
import { useLineageStore } from "../lineageStore";

vi.mock("../../api/endpoints", () => ({
  getLineageGraph: vi.fn(),
}));

import { getLineageGraph } from "../../api/endpoints";

describe("lineageStore", () => {
  beforeEach(() => {
    useLineageStore.setState({ graph: null, loading: false });
    vi.clearAllMocks();
  });

  it("forwards signal to getLineageGraph", async () => {
    vi.mocked(getLineageGraph).mockResolvedValue({ nodes: [], edges: [] });
    const controller = new AbortController();
    await useLineageStore.getState().fetchGraph(undefined, controller.signal);
    expect(vi.mocked(getLineageGraph)).toHaveBeenCalledWith(undefined, controller.signal);
  });

  it("does not update state when aborted", async () => {
    vi.mocked(getLineageGraph).mockRejectedValue(new axios.CanceledError());
    const controller = new AbortController();
    controller.abort();
    await useLineageStore.getState().fetchGraph(undefined, controller.signal);
    expect(useLineageStore.getState().graph).toBeNull();
    expect(useLineageStore.getState().loading).toBe(false);
  });

  it("rethrows non-cancel errors", async () => {
    vi.mocked(getLineageGraph).mockRejectedValue(new Error("Network error"));
    await expect(useLineageStore.getState().fetchGraph()).rejects.toThrow("Network error");
    expect(useLineageStore.getState().loading).toBe(false);
  });
});
