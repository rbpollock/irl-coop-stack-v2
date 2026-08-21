"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";

const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop";

export type LiveNotification = {
  id: string;
  type: string;
  title: string;
  body: string;
  url: string;
  urgency: "low" | "normal" | "high";
  ts: number;
  read: boolean;
};

// Live notifications: one poll for history, then a fetch-based SSE stream for
// live arrivals (native EventSource can't send an Authorization header, so we
// read the SSE body directly to keep the token off the URL). Read-state is
// server-side (notification_reads): the poll returns the real `read` flag and
// markRead/clearAll persist back, so the unread badge and the digest agree on
// what "unanswered" means.
export function useNotifications() {
  const { data: session } = useSession();
  const token = session?.accessToken as string | undefined;
  const [notifications, setNotifications] = useState<LiveNotification[]>([]);
  const seenRef = useRef<Set<string>>(new Set());

  const unread = notifications.filter((n) => !n.read).length;

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    let controller: AbortController | null = null;

    const load = async () => {
      try {
        const res = await fetch(`${COOP_API_URL}/api/v1/notifications?limit=50`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return;
        const list = (await res.json()) as LiveNotification[];
        if (cancelled) return;
        list.forEach((n) => seenRef.current.add(n.id));
        setNotifications(list);
      } catch {
        /* transient — the SSE stream still delivers live arrivals */
      }
    };

    const stream = async () => {
      while (!cancelled) {
        controller = new AbortController();
        try {
          const res = await fetch(`${COOP_API_URL}/api/v1/notifications/stream`, {
            headers: {
              Authorization: `Bearer ${token}`,
              Accept: "text/event-stream",
            },
            signal: controller.signal,
          });
          if (!res.ok || !res.body) throw new Error("stream unavailable");
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buf = "";
          for (;;) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            let idx: number;
            while ((idx = buf.indexOf("\n\n")) !== -1) {
              const chunk = buf.slice(0, idx);
              buf = buf.slice(idx + 2);
              const line = chunk.split("\n").find((l) => l.startsWith("data: "));
              if (!line) continue;
              const n = JSON.parse(line.slice(6)) as LiveNotification;
              if (seenRef.current.has(n.id)) continue;
              seenRef.current.add(n.id);
              if (cancelled) return;
              setNotifications((prev) => [n, ...prev].slice(0, 50));
            }
          }
          return; // clean end — reconnect via the outer loop
        } catch {
          if (cancelled) return;
          // backoff before retry (best-effort liveness; durability is the
          // Temporal lane + the poll endpoint, not this loop)
          await new Promise((r) => setTimeout(r, 5000));
        }
      }
    };

    void load();
    void stream();

    return () => {
      cancelled = true;
      controller?.abort();
    };
  }, [token]);

  const markRead = useCallback(
    async (ids: string[]) => {
      if (!token || ids.length === 0) return;
      // optimistic: flip locally, then persist (server is the source of truth
      // for the digest; a failed write is reconciled on the next poll).
      setNotifications((prev) =>
        prev.map((n) => (ids.includes(n.id) ? { ...n, read: true } : n)),
      );
      try {
        await fetch(`${COOP_API_URL}/api/v1/notifications/read`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ event_ids: ids }),
        });
      } catch {
        /* transient — next poll reloads the authoritative read state */
      }
    },
    [token],
  );

  const clearAll = useCallback(async () => {
    if (!token) return;
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    try {
      await fetch(`${COOP_API_URL}/api/v1/notifications/clear`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {
      /* transient — next poll reloads the authoritative read state */
    }
  }, [token]);

  return { notifications, unread, markRead, clearAll, markAllRead: clearAll };
}
