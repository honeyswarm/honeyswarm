import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Table } from "../components/Table";
import { useTrackedAction } from "../hooks/useTrackedAction";

interface Hive {
  id: string;
  name: string;
  registered: boolean;
  connection_state: string;
  agent_version: string | null;
  last_heartbeat: string | null;
  grains: { osfullname?: string; ipv4?: string[] };
}

interface CreatedHive extends Hive {
  enroll_token: string;
  install_command: string;
  install_command_ssh: string;
  install_command_windows: string;
}

function HiveActions({ hive }: { hive: Hive }) {
  const qc = useQueryClient();
  const t = useTrackedAction();
  const update = useMutation({
    mutationFn: () => api<{ command_id: string }>(`/hives/${hive.id}/update-agent`, { method: "POST" }),
    onSuccess: (res) => t.track("update", res.command_id),
  });
  const remove = useMutation({
    mutationFn: () => api(`/hives/${hive.id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hives"] }),
  });

  useEffect(() => {
    if (t.phase === "done" || t.phase === "error") qc.invalidateQueries({ queryKey: ["hives"] });
  }, [t.phase, qc]);

  return (
    <div className="row">
      {t.busy && <span className="spinner" />}
      {t.phase === "done" && <span className="badge ok">agent updated ✓</span>}
      {t.phase === "error" && (
        <span className="badge off" title={t.response ?? ""}>
          update failed
        </span>
      )}
      <button
        onClick={() => update.mutate()}
        disabled={!hive.registered || t.busy || update.isPending}
        title="Pull the latest agent image and recreate the agent in place"
      >
        {t.busy ? "Updating…" : "Update agent"}
      </button>
      <button className="danger" onClick={() => remove.mutate()}>
        Delete
      </button>
    </div>
  );
}

export function Hives() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [created, setCreated] = useState<CreatedHive | null>(null);

  const hives = useQuery({
    queryKey: ["hives"],
    queryFn: () => api<Hive[]>("/hives"),
    refetchInterval: 5000,
  });

  const create = useMutation({
    mutationFn: (n: string) => api<CreatedHive>("/hives", { method: "POST", body: JSON.stringify({ name: n }) }),
    onSuccess: (data) => {
      setCreated(data);
      setName("");
      qc.invalidateQueries({ queryKey: ["hives"] });
    },
  });

  function onCreate(e: FormEvent) {
    e.preventDefault();
    if (name.trim()) create.mutate(name.trim());
  }

  return (
    <div>
      <h1>Hives</h1>

      <div className="panel">
        <h2>Enroll a new hive</h2>
        <form className="row" onSubmit={onCreate}>
          <input placeholder="Hive name" value={name} onChange={(e) => setName(e.target.value)} />
          <button type="submit" disabled={create.isPending}>
            Create &amp; get install command
          </button>
        </form>
        {create.error && <div className="error">{(create.error as Error).message}</div>}
        {created && (
          <div style={{ marginTop: 14 }}>
            <div className="label" style={{ marginBottom: 6 }}>
              Run on the hive host (installs Docker + the agent; token shown once):
            </div>
            <div className="label" style={{ marginTop: 8, marginBottom: 4 }}>Linux</div>
            <div className="code">{created.install_command}</div>
            <div className="label" style={{ marginTop: 10, marginBottom: 4 }}>
              Linux — SSH honeypot host (also moves host SSH to port 2222)
            </div>
            <div className="code">{created.install_command_ssh}</div>
            <div className="label" style={{ marginTop: 10, marginBottom: 4 }}>
              Windows (PowerShell, Docker Desktop required)
            </div>
            <div className="code">{created.install_command_windows}</div>
          </div>
        )}
      </div>

      <div className="panel">
        <Table
          columns={[
            { header: "Name", cell: (h: Hive) => h.name },
            {
              header: "State",
              cell: (h) => (
                <span className={`badge ${h.connection_state === "online" ? "ok" : "off"}`}>
                  {h.connection_state}
                </span>
              ),
            },
            { header: "Registered", cell: (h) => (h.registered ? "yes" : "no") },
            { header: "OS", cell: (h) => h.grains?.osfullname ?? "—" },
            { header: "IPs", cell: (h) => (h.grains?.ipv4 ?? []).join(", ") || "—" },
            { header: "Agent", cell: (h) => h.agent_version ?? "—" },
            {
              header: "",
              cell: (h) => <HiveActions hive={h} />,
            },
          ]}
          rows={hives.data ?? []}
          empty="No hives enrolled yet."
        />
      </div>
    </div>
  );
}
