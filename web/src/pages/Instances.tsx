import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Table } from "../components/Table";
import { useTrackedAction } from "../hooks/useTrackedAction";

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

function InstanceActions({ instance }: { instance: Instance }) {
  const qc = useQueryClient();
  const t = useTrackedAction();
  const action = useMutation({
    mutationFn: ({ verb }: { verb: string }) =>
      verb === "remove"
        ? api<{ command_id: string }>(`/instances/${instance.id}`, { method: "DELETE" })
        : api<{ command_id: string }>(`/instances/${instance.id}/${verb}`, { method: "POST" }),
    onSuccess: (res, { verb }) => {
      t.track(verb, res.command_id);
      qc.invalidateQueries({ queryKey: ["instances"] });
    },
  });

  // Refresh the table when the job lands so the status badge reflects reality.
  useEffect(() => {
    if (t.phase === "done" || t.phase === "error") qc.invalidateQueries({ queryKey: ["instances"] });
  }, [t.phase, qc]);

  if (t.busy) {
    return (
      <span className="row">
        <span className="spinner" /> <span className="label">{t.verb}…</span>
      </span>
    );
  }

  return (
    <div className="row">
      {t.phase === "done" && <span className="badge ok">{t.verb} ✓</span>}
      {t.phase === "error" && (
        <span className="badge off" title={t.response ?? ""}>
          {t.verb} failed
        </span>
      )}
      <button className="secondary" disabled={action.isPending} onClick={() => action.mutate({ verb: "start" })}>
        Start
      </button>
      <button className="secondary" disabled={action.isPending} onClick={() => action.mutate({ verb: "stop" })}>
        Stop
      </button>
      <button className="danger" disabled={action.isPending} onClick={() => action.mutate({ verb: "remove" })}>
        Remove
      </button>
    </div>
  );
}

export function Instances() {
  const qc = useQueryClient();
  const [honeypotId, setHoneypotId] = useState("");
  const [hiveId, setHiveId] = useState("");
  const deployTrack = useTrackedAction();

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
      api<{ command_id: string }>("/instances/deploy", {
        method: "POST",
        body: JSON.stringify({ honeypot_id: honeypotId, hive_id: hiveId }),
      }),
    onSuccess: (res) => {
      deployTrack.track("deploy", res.command_id);
      qc.invalidateQueries({ queryKey: ["instances"] });
    },
  });

  useEffect(() => {
    if (deployTrack.phase === "done" || deployTrack.phase === "error") {
      qc.invalidateQueries({ queryKey: ["instances"] });
    }
  }, [deployTrack.phase, qc]);

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
          <button type="submit" disabled={!honeypotId || !hiveId || deploy.isPending || deployTrack.busy}>
            {deployTrack.busy ? "Deploying…" : "Deploy"}
          </button>
          {deployTrack.busy && <span className="spinner" />}
          {deployTrack.phase === "done" && <span className="badge ok">Deployed ✓</span>}
          {deployTrack.phase === "error" && (
            <span className="badge off" title={deployTrack.response ?? ""}>
              Deploy failed
            </span>
          )}
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
              cell: (i) => <InstanceActions instance={i} />,
            },
          ]}
          rows={instances.data ?? []}
          empty="No instances deployed."
        />
      </div>
    </div>
  );
}
