import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export interface JobStatus {
  command_id: string;
  status: string; // pending | running | complete | failed
  complete: boolean;
  job_response: string | null;
}

/** Poll a job (by its command id) until it completes. */
export function useJobStatus(commandId: string | null) {
  return useQuery({
    queryKey: ["job", commandId],
    enabled: !!commandId,
    queryFn: () => api<JobStatus>(`/jobs/${commandId}`),
    refetchInterval: (query) => (query.state.data?.complete ? false : 1000),
    staleTime: 0,
  });
}
