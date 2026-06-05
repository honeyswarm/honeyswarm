import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Table } from "../components/Table";

interface Bucket {
  key: string;
  doc_count: number;
}
interface Stats {
  total: number;
  by_service: Bucket[];
  by_honeypot: Bucket[];
  top_sources: Bucket[];
}
interface Hive {
  id: string;
  name: string;
  connection_state: string;
}

export function Dashboard() {
  const stats = useQuery({
    queryKey: ["stats"],
    queryFn: () => api<Stats>("/events/stats"),
    refetchInterval: 5000,
  });
  const hives = useQuery({ queryKey: ["hives"], queryFn: () => api<Hive[]>("/hives") });

  const online = hives.data?.filter((h) => h.connection_state === "online").length ?? 0;

  return (
    <div>
      <h1>Dashboard</h1>
      <div className="honeycomb">
        {[
          { value: stats.data?.total ?? "—", label: "Total events" },
          { value: `${online}/${hives.data?.length ?? 0}`, label: "Hives online" },
          { value: stats.data?.by_honeypot.length ?? "—", label: "Honeypot types" },
          { value: stats.data?.top_sources.length ?? "—", label: "Top attackers" },
        ].map((tile) => (
          <div className="hex" key={tile.label}>
            <div className="outer" />
            <div className="inner">
              <div className="value">{tile.value}</div>
              <div className="label">{tile.label}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="panel">
        <h2>Events by service</h2>
        <Table
          columns={[
            { header: "Service", cell: (b: Bucket) => b.key },
            { header: "Events", cell: (b: Bucket) => b.doc_count },
          ]}
          rows={stats.data?.by_service ?? []}
          empty="No events yet."
        />
      </div>

      <div className="panel">
        <h2>Top source IPs</h2>
        <Table
          columns={[
            { header: "Source IP", cell: (b: Bucket) => b.key },
            { header: "Events", cell: (b: Bucket) => b.doc_count },
          ]}
          rows={stats.data?.top_sources ?? []}
          empty="No events yet."
        />
      </div>
    </div>
  );
}
