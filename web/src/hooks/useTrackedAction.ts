import { useEffect, useState } from "react";
import { useJobStatus } from "./useJobStatus";

export type Phase = "idle" | "running" | "done" | "error";

/**
 * Tracks one in-flight command through its job lifecycle for button feedback.
 * Call `track(verb, command_id)` from a mutation's onSuccess; read `phase`,
 * `verb`, `busy` and `response` to render state. Completed state auto-clears.
 */
export function useTrackedAction(clearAfterMs = 3000) {
  const [commandId, setCommandId] = useState<string | null>(null);
  const [verb, setVerb] = useState("");
  const job = useJobStatus(commandId);
  const complete = job.data?.complete ?? false;

  useEffect(() => {
    if (!commandId || !complete) return;
    const t = setTimeout(() => setCommandId(null), clearAfterMs);
    return () => clearTimeout(t);
  }, [commandId, complete, clearAfterMs]);

  const phase: Phase = !commandId
    ? "idle"
    : !complete
      ? "running"
      : job.data?.status === "failed"
        ? "error"
        : "done";

  return {
    phase,
    verb,
    busy: phase === "running",
    response: job.data?.job_response ?? null,
    track: (v: string, id: string) => {
      setVerb(v);
      setCommandId(id);
    },
  };
}
