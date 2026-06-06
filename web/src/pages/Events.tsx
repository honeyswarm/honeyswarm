import { useEffect, useRef, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, tokens } from "../api/client";
import { Table } from "../components/Table";

const PAGE_SIZE = 50;
// OpenSearch's default from+size result window; deeper pages would error.
const MAX_WINDOW = 10000;

interface Event {
  date: string;
  service: string;
  port: number;
  honeypot_type: string;
  source_ip: string;
  hive_id: string;
  honeypot_instance_id?: string;
  event_id?: string;
  payload?: Record<string, unknown>;
}
interface EventPage {
  total: number;
  page: number;
  page_size: number;
  results: Event[];
}
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
interface HiveLite {
  id: string;
  name: string;
}

function EventDetail({ e, hiveName }: { e: Event; hiveName: string }) {
  return (
    <div className="event-detail">
      <div className="kv-grid">
        <div>
          <span className="k">Time</span>
          <span className="v">{new Date(e.date).toLocaleString()}</span>
        </div>
        <div>
          <span className="k">Hive</span>
          <span className="v">
            {e.hive_id ? (
              <Link to="/hives" onClick={(ev) => ev.stopPropagation()}>
                {hiveName}
              </Link>
            ) : (
              "—"
            )}
          </span>
        </div>
        <div>
          <span className="k">Instance</span>
          <span className="v mono">{e.honeypot_instance_id ?? "—"}</span>
        </div>
        <div>
          <span className="k">Event ID</span>
          <span className="v mono">{e.event_id ?? "—"}</span>
        </div>
      </div>
      <div className="raw">
        <span className="k">Raw payload</span>
        <pre>{JSON.stringify(e.payload ?? {}, null, 2)}</pre>
      </div>
    </div>
  );
}

export function Events() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [live, setLive] = useState(false);

  const events = useQuery({
    queryKey: ["events", query, page],
    queryFn: () =>
      api<EventPage>(
        `/events?page=${page}&page_size=${PAGE_SIZE}${
          query ? `&search=${encodeURIComponent(query)}` : ""
        }`,
      ),
    refetchInterval: live ? false : 8000,
    placeholderData: keepPreviousData, // keep the current page visible while the next loads
  });

  const total = events.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(Math.min(total, MAX_WINDOW) / PAGE_SIZE));

  // Clamp the page if the result set shrank (new filter, fewer matches).
  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const runSearch = () => {
    setQuery(search);
    setPage(1);
  };

  const stats = useQuery({
    queryKey: ["stats"],
    queryFn: () => api<Stats>("/events/stats"),
    refetchInterval: live ? false : 8000,
  });

  const hives = useQuery({ queryKey: ["hives"], queryFn: () => api<HiveLite[]>("/hives") });
  const hiveName = (id?: string) =>
    (id && hives.data?.find((h) => h.id === id)?.name) || id || "—";

  const topSource = stats.data?.top_sources?.[0];

  // Live updates over WebSocket.
  const wsRef = useRef<WebSocket | null>(null);
  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws?token=${tokens.access ?? ""}`);
    ws.onopen = () => setLive(true);
    ws.onclose = () => setLive(false);
    ws.onmessage = (msg) => {
      try {
        const { channel } = JSON.parse(msg.data);
        if (channel === "events") {
          events.refetch();
          stats.refetch();
        }
      } catch {
        /* ignore */
      }
    };
    wsRef.current = ws;
    return () => ws.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <h1>
        Events {live && <span className="live">● live</span>}
      </h1>

      <div className="cards">
        <div className="card">
          <div className="value">{stats.data?.total ?? "—"}</div>
          <div className="label">Total events</div>
        </div>
        <div className="card">
          <div className="value">{stats.data?.by_honeypot.length ?? "—"}</div>
          <div className="label">Honeypot types</div>
        </div>
        <div className="card">
          <div className="value">{stats.data?.by_service.length ?? "—"}</div>
          <div className="label">Services seen</div>
        </div>
        <div className="card">
          <div className="value mono">{topSource?.key ?? "—"}</div>
          <div className="label">
            Top attacker{topSource ? ` · ${topSource.doc_count} hits` : ""}
          </div>
        </div>
      </div>

      <div className="panel">
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault();
            runSearch();
          }}
        >
          <input
            style={{ flex: 1 }}
            placeholder="Search: ip:1.2.3.4 · service:SSH · port:22 · honeypot:Cowrie"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button type="submit">Search</button>
          {query && (
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setSearch("");
                setQuery("");
                setPage(1);
              }}
            >
              Clear
            </button>
          )}
          <span className="spacer" />
          <span className="label">{total} matches</span>
        </form>
      </div>

      <div className="panel">
        <Table
          columns={[
            { header: "Time", cell: (e: Event) => new Date(e.date).toLocaleString() },
            { header: "Service", cell: (e) => e.service },
            { header: "Port", cell: (e) => e.port },
            { header: "Honeypot", cell: (e) => e.honeypot_type },
            { header: "Source IP", cell: (e) => e.source_ip || "—" },
            {
              header: "Hive",
              cell: (e) =>
                e.hive_id ? (
                  <Link to="/hives" onClick={(ev) => ev.stopPropagation()}>
                    {hiveName(e.hive_id)}
                  </Link>
                ) : (
                  "—"
                ),
            },
          ]}
          rows={events.data?.results ?? []}
          rowKey={(e, i) => e.event_id ?? i}
          expandedContent={(e) => <EventDetail e={e} hiveName={hiveName(e.hive_id)} />}
          empty="No matching events."
        />

        <div className="row pager">
          <button
            type="button"
            className="secondary"
            disabled={page <= 1 || events.isFetching}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            ← Prev
          </button>
          <span className="label">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            className="secondary"
            disabled={page >= totalPages || events.isFetching}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            Next →
          </button>
          {events.isFetching && <span className="spinner" />}
          <span className="spacer" />
          <span className="label">
            Showing {total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1}–
            {Math.min(page * PAGE_SIZE, total)} of {total}
          </span>
        </div>
      </div>
    </div>
  );
}
