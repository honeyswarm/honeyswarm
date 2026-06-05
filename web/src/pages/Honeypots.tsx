import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Table } from "../components/Table";

interface Honeypot {
  id: string;
  name: string;
  honey_type: string | null;
  description: string | null;
  manifest: string | null;
  normalizer: string | null;
}

export function Honeypots() {
  const qc = useQueryClient();
  const honeypots = useQuery({ queryKey: ["honeypots"], queryFn: () => api<Honeypot[]>("/honeypots") });
  const available = useQuery({ queryKey: ["manifests"], queryFn: () => api<string[]>("/honeypots/available") });

  const importHp = useMutation({
    mutationFn: (manifest: string) => api(`/honeypots/import/${manifest}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["honeypots"] }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/honeypots/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["honeypots"] }),
  });

  const imported = new Set((honeypots.data ?? []).map((h) => h.manifest));

  return (
    <div>
      <h1>Honeypots</h1>

      <div className="panel">
        <h2>Available manifests</h2>
        {importHp.error && <div className="error">{(importHp.error as Error).message}</div>}
        <div className="row">
          {(available.data ?? []).map((m) => (
            <button
              key={m}
              className="secondary"
              disabled={imported.has(m) || importHp.isPending}
              onClick={() => importHp.mutate(m)}
            >
              {imported.has(m) ? `${m} ✓` : `Import ${m}`}
            </button>
          ))}
          {available.data?.length === 0 && <span className="label">No manifests on disk.</span>}
        </div>
      </div>

      <div className="panel">
        <h2>Definitions</h2>
        <Table
          columns={[
            { header: "Name", cell: (h: Honeypot) => h.name },
            { header: "Type", cell: (h) => h.honey_type ?? "—" },
            { header: "Normalizer", cell: (h) => h.normalizer ?? "—" },
            { header: "Manifest", cell: (h) => h.manifest ?? "—" },
            {
              header: "",
              cell: (h) => (
                <button className="danger" onClick={() => remove.mutate(h.id)}>
                  Delete
                </button>
              ),
            },
          ]}
          rows={honeypots.data ?? []}
          empty="No honeypot definitions. Import one above."
        />
      </div>
    </div>
  );
}
