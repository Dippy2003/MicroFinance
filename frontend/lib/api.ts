// Client-side helper for talking to the FastAPI backend.

import type { AdviceResponse, BorrowerProfile, StreamFrame } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export interface StreamHandlers {
  onLine: (line: string) => void;
  onResult: (result: AdviceResponse) => void;
  onError: (message: string) => void;
  onDone: () => void;
}

/**
 * Open an SSE stream to GET /advise/stream and dispatch frames to handlers.
 *
 * The backend's SSE endpoint is GET-only (EventSource cannot POST), so the
 * profile is JSON-encoded into the `profile` query param, matching the backend.
 * Returns the EventSource so the caller can close() it on unmount.
 */
export function streamAdvice(
  profile: BorrowerProfile,
  incomeChangeTo: number | null,
  handlers: StreamHandlers,
): EventSource {
  const params = new URLSearchParams({ profile: JSON.stringify(profile) });
  if (incomeChangeTo != null) {
    params.set("income_change_to", String(incomeChangeTo));
  }

  const es = new EventSource(`${API_BASE}/advise/stream?${params.toString()}`);

  es.onmessage = (event) => {
    let frame: StreamFrame;
    try {
      frame = JSON.parse(event.data) as StreamFrame;
    } catch {
      return; // ignore malformed frames
    }

    if ("line" in frame) handlers.onLine(frame.line);
    else if ("result" in frame) handlers.onResult(frame.result);
    else if ("error" in frame) handlers.onError(frame.error);
    else if ("done" in frame) {
      handlers.onDone();
      es.close(); // server is finished; stop reconnect attempts
    }
  };

  // EventSource auto-reconnects on network errors; for our one-shot run we treat
  // any error after the stream has started as terminal and close it.
  es.onerror = () => {
    handlers.onError("Connection to the agent stream was lost.");
    es.close();
  };

  return es;
}
