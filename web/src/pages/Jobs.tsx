import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Table } from "../components/Table";

interface Job {
  id: string;
  job_type: string;
  job_description: string;
  status?: string;
  complete: boolean;
  created_at: string;
  completed_at: string | null;
  job_response: string | null;
}

export function Jobs() {
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<Job[]>("/jobs?limit=100"),
    refetchInterval: 4000,
  });

  return (
    <div>
      <h1>Jobs</h1>
      <div className="panel">
        <Table
          columns={[
            { header: "Type", cell: (j: Job) => j.job_type },
            { header: "Description", cell: (j) => j.job_description },
            {
              header: "Status",
              cell: (j) => {
                const s = j.status ?? (j.complete ? "complete" : "pending");
                const cls = s === "complete" ? "ok" : s === "failed" ? "off" : s === "running" ? "warn" : "neutral";
                return <span className={`badge ${cls}`}>{s}</span>;
              },
            },
            { header: "Created", cell: (j) => new Date(j.created_at).toLocaleString() },
            { header: "Response", cell: (j) => j.job_response ?? "—" },
          ]}
          rows={jobs.data ?? []}
          empty="No jobs yet."
        />
      </div>
    </div>
  );
}
