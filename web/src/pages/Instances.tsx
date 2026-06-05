import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Table } from "../components/Table";

interface Instance {
  id: string;
  honeypot: string | null;
  hive: string | null;
  status: string;
}
interface Honeypot {
  id: string;
  name: string;
}
interface Hive {
  id: string;
  name: string;
  registered: boolean;
}

export function Instances() {
  const qc = useQueryClient();
  const [honeypotId, setHoneypotId] = useState("");
  const [hiveId, setHiveId] = useState("");

  const instances = useQuery({
    queryKey: ["instances"],
    queryFn: () => api<Instance[]>("/instances"),
    refetchInterval: 4000,
  });
  const honeypots = useQuery({ queryKey: ["honeypots"], queryFn: () => api<Honeypot[]>("/honeypots") });
  const hives = useQuery({ queryKey: ["hives"], queryFn: () => api<Hive[]>("/hives") });

  const nameOf = (list: { id: string; name: string }[] | undefined, id: string | null) =>
    list?.find((x) => x.id === id)?.name ?? id ?? "—";

  const deploy = useMutation({
    mutationFn: () =>
      api("/instances/deploy", {
        method: "POST",
        body: JSON.stringify({ honeypot_id: honeypotId, hive_id: hiveId }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["instances"] }),
  });
  const action = useMutation({
    mutationFn: ({ id, verb }: { id: string; verb: string }) =>
      verb === "remove"
        ? api(`/instances/${id}`, { method: "DELETE" })
        : api(`/instances/${id}/${verb}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["instances"] }),
  });

  function onDeploy(e: FormEvent) {
    e.preventDefault();
    if (honeypotId && hiveId) deploy.mutate();
  }

  return (
    <div>
      <h1>Instances</h1>

      <div className="panel">
        <h2>Deploy a honeypot</h2>
        {deploy.error && <div className="error">{(deploy.error as Error).message}</div>}
        <form className="row" onSubmit={onDeploy}>
          <select value={honeypotId} onChange={(e) => setHoneypotId(e.target.value)}>
            <option value="">Select honeypot…</option>
            {(honeypots.data ?? []).map((h) => (
              <option key={h.id} value={h.id}>
                {h.name}
              </option>
            ))}
          </select>
          <select value={hiveId} onChange={(e) => setHiveId(e.target.value)}>
            <option value="">Select hive…</option>
            {(hives.data ?? [])
              .filter((h) => h.registered)
              .map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name}
                </option>
              ))}
          </select>
          <button type="submit" disabled={!honeypotId || !hiveId || deploy.isPending}>
            Deploy
          </button>
        </form>
      </div>

      <div className="panel">
        <Table
          columns={[
            { header: "Honeypot", cell: (i: Instance) => nameOf(honeypots.data, i.honeypot) },
            { header: "Hive", cell: (i) => nameOf(hives.data, i.hive) },
            {
              header: "Status",
              cell: (i) => (
                <span className={`badge ${i.status === "Running" ? "ok" : "neutral"}`}>{i.status}</span>
              ),
            },
            {
              header: "Actions",
              cell: (i) => (
                <div className="row">
                  <button className="secondary" onClick={() => action.mutate({ id: i.id, verb: "start" })}>
                    Start
                  </button>
                  <button className="secondary" onClick={() => action.mutate({ id: i.id, verb: "stop" })}>
                    Stop
                  </button>
                  <button className="danger" onClick={() => action.mutate({ id: i.id, verb: "remove" })}>
                    Remove
                  </button>
                </div>
              ),
            },
          ]}
          rows={instances.data ?? []}
          empty="No instances deployed."
        />
      </div>
    </div>
  );
}
