import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, tokens } from "../api/client";
import { Table } from "../components/Table";

interface Event {
  date: string;
  service: string;
  port: number;
  honeypot_type: string;
  source_ip: string;
  hive_id: string;
}
interface EventPage {
  total: number;
  page: number;
  page_size: number;
  results: Event[];
}

export function Events() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [live, setLive] = useState(false);

  const events = useQuery({
    queryKey: ["events", query],
    queryFn: () =>
      api<EventPage>(`/events?page_size=50${query ? `&search=${encodeURIComponent(query)}` : ""}`),
    refetchInterval: live ? false : 8000,
  });

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
        if (channel === "events") events.refetch();
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
      <div className="panel">
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault();
            setQuery(search);
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
              }}
            >
              Clear
            </button>
          )}
          <span className="spacer" />
          <span className="label">{events.data?.total ?? 0} matches</span>
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
          ]}
          rows={events.data?.results ?? []}
          empty="No matching events."
        />
      </div>
    </div>
  );
}
