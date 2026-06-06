import { FormEvent, lazy, Suspense, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import yaml from "js-yaml";
import { api } from "../api/client";
import { Table } from "../components/Table";

// Lazily loaded so CodeMirror is fetched only when the editor opens.
const CodeEditor = lazy(() =>
  import("../components/CodeEditor").then((m) => ({ default: m.CodeEditor })),
);

interface Honeypot {
  id: string;
  name: string;
  honey_type: string | null;
  description: string | null;
  manifest: string | null;
  normalizer: string | null;
}

interface ManifestDoc {
  manifest_yaml: string;
  config_text: string | null;
  config_filename: string | null;
}

export function Honeypots() {
  const qc = useQueryClient();
  const honeypots = useQuery({ queryKey: ["honeypots"], queryFn: () => api<Honeypot[]>("/honeypots") });
  const available = useQuery({ queryKey: ["manifests"], queryFn: () => api<string[]>("/honeypots/available") });
  const normalizers = useQuery({ queryKey: ["normalizers"], queryFn: () => api<string[]>("/honeypots/normalizers") });

  const [newName, setNewName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");
  const [manifestYaml, setManifestYaml] = useState("");
  const [configText, setConfigText] = useState("");
  const [configFilename, setConfigFilename] = useState<string | null>(null);

  // Detect a config file declared in the manifest the user is editing, so the
  // config editor appears/disappears live (also covers configs added from scratch).
  useEffect(() => {
    if (!editingId) return;
    try {
      const m = yaml.load(manifestYaml) as { config?: { template?: unknown } } | null;
      const tpl = m && typeof m === "object" ? m.config?.template : null;
      setConfigFilename(typeof tpl === "string" ? tpl : null);
    } catch {
      /* invalid YAML mid-edit — keep the last known config state */
    }
  }, [manifestYaml, editingId]);

  const importHp = useMutation({
    mutationFn: (manifest: string) => api(`/honeypots/import/${manifest}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["honeypots"] }),
  });
  const create = useMutation({
    mutationFn: (name: string) => api<Honeypot>("/honeypots", { method: "POST", body: JSON.stringify({ name }) }),
    onSuccess: (hp) => {
      qc.invalidateQueries({ queryKey: ["honeypots"] });
      setNewName("");
      startEdit(hp); // jump straight into the editor for the new definition
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/honeypots/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["honeypots"] }),
  });
  const save = useMutation({
    mutationFn: () =>
      api(`/honeypots/${editingId}/manifest`, {
        method: "PUT",
        body: JSON.stringify({
          manifest_yaml: manifestYaml,
          config_text: configFilename ? configText : null,
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["honeypots"] });
      setEditingId(null);
    },
  });

  async function startEdit(h: Honeypot) {
    save.reset();
    const doc = await api<ManifestDoc>(`/honeypots/${h.id}/manifest`);
    setEditingId(h.id);
    setEditingName(h.name);
    setManifestYaml(doc.manifest_yaml);
    setConfigText(doc.config_text ?? "");
    setConfigFilename(doc.config_filename);
  }

  function onCreate(e: FormEvent) {
    e.preventDefault();
    if (newName.trim()) create.mutate(newName.trim());
  }

  const imported = new Set((honeypots.data ?? []).map((h) => h.manifest));

  return (
    <div>
      <h1>Honeypots</h1>

      <div className="panel">
        <h2>Create a honeypot</h2>
        <div className="label" style={{ marginBottom: 8 }}>
          Build your own from scratch — you'll get a starter manifest to edit.
        </div>
        {create.error && <div className="error">{(create.error as Error).message}</div>}
        <form className="row" onSubmit={onCreate}>
          <input placeholder="Honeypot name" value={newName} onChange={(e) => setNewName(e.target.value)} />
          <button type="submit" disabled={create.isPending || !newName.trim()}>
            Create &amp; edit
          </button>
        </form>
        <div className="label" style={{ marginTop: 10 }}>
          Or import a built-in manifest:
        </div>
        {importHp.error && <div className="error">{(importHp.error as Error).message}</div>}
        <div className="row" style={{ marginTop: 6 }}>
          {(available.data ?? []).map((m) => (
            <button
              key={m}
              className="secondary"
              disabled={imported.has(m) || importHp.isPending}
              onClick={() => importHp.mutate(m)}
            >
              {imported.has(m) ? `${m} ✓` : `Add ${m}`}
            </button>
          ))}
          {available.data?.length === 0 && <span className="label">No manifests on disk.</span>}
        </div>
      </div>

      {editingId && (
        <div className="panel">
          <div className="row">
            <h2 style={{ margin: 0 }}>Edit {editingName}</h2>
            <span className="spacer" />
            <button className="secondary" onClick={() => setEditingId(null)}>
              Cancel
            </button>
            <button onClick={() => save.mutate()} disabled={save.isPending}>
              Save
            </button>
          </div>
          <div className="label" style={{ marginTop: 4 }}>
            Editing the stored copy (not a file on disk). Add a <code>config:</code> block with a{" "}
            <code>template</code> + <code>mount</code> to get a config-file editor. With{" "}
            <code>normalizer: generic</code> you can add <code>log.field_map</code> (canonical field →
            payload key, dot-notation) and <code>log.static</code> (literal values) to map a custom
            honeypot's JSON.
            {normalizers.data && <> Normalizers: {normalizers.data.join(", ")}.</>}
          </div>
          {save.error && <div className="error" style={{ marginTop: 8 }}>{(save.error as Error).message}</div>}

          <Suspense fallback={<div className="label" style={{ marginTop: 12 }}>Loading editor…</div>}>
            <div className="label" style={{ marginTop: 12, marginBottom: 4 }}>Manifest (YAML)</div>
            <CodeEditor language="yaml" value={manifestYaml} onChange={setManifestYaml} />

            {configFilename && (
              <>
                <div className="label" style={{ marginTop: 12, marginBottom: 4 }}>
                  Config file — {configFilename}
                </div>
                <CodeEditor language="ini" value={configText} onChange={setConfigText} />
              </>
            )}
          </Suspense>
        </div>
      )}

      <div className="panel">
        <h2>Definitions</h2>
        <Table
          columns={[
            { header: "Name", cell: (h: Honeypot) => h.name },
            { header: "Type", cell: (h) => h.honey_type ?? "—" },
            { header: "Normalizer", cell: (h) => h.normalizer ?? "—" },
            { header: "Source", cell: (h) => h.manifest ?? "custom" },
            {
              header: "",
              cell: (h) => (
                <div className="row">
                  <button className="secondary" onClick={() => startEdit(h)}>
                    Edit
                  </button>
                  <button className="danger" onClick={() => remove.mutate(h.id)}>
                    Delete
                  </button>
                </div>
              ),
            },
          ]}
          rows={honeypots.data ?? []}
          empty="No honeypot definitions yet. Create or import one above."
        />
      </div>
    </div>
  );
}
