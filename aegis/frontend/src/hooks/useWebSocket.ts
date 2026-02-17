import { useEffect, useRef, useCallback } from "react";
import type { WsEvent } from "../api/types";

const WS_URL = import.meta.env.VITE_WS_URL || `ws://${window.location.host}/ws`;

/**
 * Auto-reconnecting WebSocket hook with exponential backoff.
 */
export function useWebSocket(onMessage: (event: WsEvent) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const maxDelay = 30_000;

  const connect = useCallback(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      retriesRef.current = 0;
    };

    ws.onmessage = (e) => {
      try {
        const parsed: WsEvent = JSON.parse(e.data);
        onMessage(parsed);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      const delay = Math.min(1000 * 2 ** retriesRef.current, maxDelay);
      retriesRef.current += 1;
      setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [onMessage]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  return wsRef;
}
