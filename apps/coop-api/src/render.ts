// Render a raw event row into a user-facing notification. Source-rendered for
// now (a keyed bus-side map — the design's open decision #4 leans bus-side),
// but the map is deliberately tiny so it can move behind source-supplied
// templates later without touching any consumer.

export type Notification = {
  id: string;
  type: string;
  title: string;
  body: string;
  url: string;
  urgency: "low" | "normal" | "high";
  ts: number;
  read: boolean;
};

export type EventRow = {
  id: string;
  type: string;
  payload?: unknown;
  occurred_at: string | Date;
};

const TITLES: Record<string, string> = {
  "m.room.message": "New message",
  "m.room.encrypted": "New encrypted message",
  "m.room.member": "Membership change",
  "m.reaction": "New reaction",
  "m.room.name": "Room renamed",
  "m.room.topic": "Room topic changed",
  "m.room.create": "Room created",
  "mail.received": "New email",
};

const URGENCY: Record<string, Notification["urgency"]> = {
  "m.room.message": "normal",
  "m.room.encrypted": "normal",
  "m.room.member": "low",
  "m.reaction": "low",
  "m.room.name": "low",
  "m.room.topic": "low",
  "m.room.create": "low",
  "mail.received": "normal",
};

export function renderNotification(row: EventRow): Notification {
  const p = (row.payload ?? {}) as Record<string, unknown>;
  const type = row.type || "event";
  const senderRaw = p.sender ?? p.from;
  const sender =
    typeof senderRaw === "string" ? senderRaw.replace(/^@/, "").split(":")[0] : "";
  const room = typeof p.room === "string" ? p.room : "";

  const title = TITLES[type] ?? `Event: ${type}`;
  let body: string;
  if (type === "mail.received") {
    body = sender ? `from ${sender}` : "New email";
  } else if (type === "m.room.message") {
    body = sender ? `${sender} posted${room ? ` in ${room}` : ""}` : "New activity";
  } else if (type === "m.room.member") {
    body = sender ? `${sender}${room ? ` · ${room}` : ""}` : "Membership changed";
  } else {
    body = room || type;
  }

  return {
    id: row.id,
    type,
    title,
    body,
    url: type.startsWith("mail.") ? "https://webmail.irl.coop" : "/apps/chat",
    urgency: URGENCY[type] ?? "low",
    ts: new Date(row.occurred_at).getTime(),
    read: false,
  };
}
