import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Table } from "../components/Table";

interface AdminUser {
  id: string;
  email: string;
  name: string | null;
  roles: string[];
  active: boolean;
}

const ALL_ROLES = ["admin", "user", "editor", "deploy"];

export function Admin() {
  const qc = useQueryClient();
  const users = useQuery({ queryKey: ["users"], queryFn: () => api<AdminUser[]>("/admin/users") });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["users"] });

  const setActive = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api(`/admin/users/${id}/${active ? "activate" : "deactivate"}`, { method: "POST" }),
    onSuccess: invalidate,
  });
  const setRoles = useMutation({
    mutationFn: ({ id, roles }: { id: string; roles: string[] }) =>
      api(`/admin/users/${id}/roles`, { method: "PUT", body: JSON.stringify({ roles }) }),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/admin/users/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });

  function toggleRole(u: AdminUser, role: string) {
    const roles = u.roles.includes(role) ? u.roles.filter((r) => r !== role) : [...u.roles, role];
    setRoles.mutate({ id: u.id, roles });
  }

  return (
    <div>
      <h1>Admin — Users</h1>
      <div className="panel">
        <Table
          columns={[
            { header: "Email", cell: (u: AdminUser) => u.email },
            { header: "Name", cell: (u) => u.name ?? "—" },
            {
              header: "Active",
              cell: (u) => (
                <span className={`badge ${u.active ? "ok" : "off"}`}>{u.active ? "active" : "inactive"}</span>
              ),
            },
            {
              header: "Roles",
              cell: (u) => (
                <div className="row">
                  {ALL_ROLES.map((r) => (
                    <button
                      key={r}
                      className={u.roles.includes(r) ? "" : "secondary"}
                      onClick={() => toggleRole(u, r)}
                    >
                      {r}
                    </button>
                  ))}
                </div>
              ),
            },
            {
              header: "Actions",
              cell: (u) => (
                <div className="row">
                  <button
                    className="secondary"
                    onClick={() => setActive.mutate({ id: u.id, active: !u.active })}
                  >
                    {u.active ? "Deactivate" : "Activate"}
                  </button>
                  <button className="danger" onClick={() => remove.mutate(u.id)}>
                    Delete
                  </button>
                </div>
              ),
            },
          ]}
          rows={users.data ?? []}
          empty="No users."
        />
      </div>
    </div>
  );
}
