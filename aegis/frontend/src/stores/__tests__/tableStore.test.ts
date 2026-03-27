import { vi, it, expect, beforeEach, describe } from "vitest";
import axios from "axios";
import { useTableStore } from "../tableStore";

vi.mock("../../api/endpoints", () => ({
  getTables: vi.fn(),
}));

import { getTables } from "../../api/endpoints";

describe("tableStore", () => {
  beforeEach(() => {
    useTableStore.setState({ tables: [], loading: false });
    vi.clearAllMocks();
  });

  it("forwards signal to getTables", async () => {
    vi.mocked(getTables).mockResolvedValue([]);
    const controller = new AbortController();
    await useTableStore.getState().fetchTables(undefined, controller.signal);
    expect(vi.mocked(getTables)).toHaveBeenCalledWith(undefined, controller.signal);
  });

  it("does not update state when aborted", async () => {
    vi.mocked(getTables).mockRejectedValue(new axios.CanceledError());
    const controller = new AbortController();
    controller.abort();
    await useTableStore.getState().fetchTables(undefined, controller.signal);
    expect(useTableStore.getState().tables).toEqual([]);
    expect(useTableStore.getState().loading).toBe(false);
  });

  it("does not update state on network error (rethrows)", async () => {
    vi.mocked(getTables).mockRejectedValue(new Error("Network error"));
    await expect(useTableStore.getState().fetchTables()).rejects.toThrow("Network error");
    expect(useTableStore.getState().loading).toBe(false);
  });
});
