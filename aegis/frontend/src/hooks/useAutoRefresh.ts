import { useEffect, useRef } from "react";

/**
 * Polling hook — calls `fn` every `intervalMs` milliseconds.
 */
export function useAutoRefresh(fn: () => void, intervalMs: number = 30_000) {
  const savedFn = useRef(fn);
  savedFn.current = fn;

  useEffect(() => {
    savedFn.current();
    const id = setInterval(() => savedFn.current(), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
}
