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
  // Hi.Events → bus (see hi-events.ts); the group's own ticketing activity
  "order.created": "New order",
  "order.paid": "Order paid",
  "order.refunded": "Order refunded",
  "order.cancelled": "Order cancelled",
  "attendee.registered": "New attendee",
  "attendee.cancelled": "Attendee cancelled",
  "checkin.recorded": "Check-in",
  "event.created": "New event",
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
  "order.created": "normal",
  "order.paid": "normal",
  "order.refunded": "low",
  "order.cancelled": "low",
  "attendee.registered": "normal",
  "attendee.cancelled": "low",
  "checkin.recorded": "low",
  "event.created": "normal",
};

const TICKET_TYPES = new Set([
  "order.created",
  "order.paid",
  "order.refunded",
  "order.cancelled",
  "attendee.registered",
  "attendee.cancelled",
  "checkin.recorded",
  "event.created",
]);

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
  } else if (TICKET_TYPES.has(type)) {
    // Counts, not people (see hi-events.ts): the event title plus a count.
    const fields = (p.fields ?? {}) as Record<string, unknown>;
    const counts = (p.counts ?? {}) as Record<string, number>;
    const eventTitle =
      typeof fields.title === "string"
        ? fields.title
        : typeof fields.name === "string"
          ? fields.name
          : "";
    const tickets = counts.order_items || counts.attendees || 0;
    body =
      [eventTitle, tickets ? `${tickets} ticket${tickets === 1 ? "" : "s"}` : ""]
        .filter(Boolean)
        .join(" · ") || type;
  } else {
    body = room || type;
  }

  const explicitLink = typeof p.link === "string" ? p.link : "";

  return {
    id: row.id,
    type,
    title,
    body,
    url:
      explicitLink ||
      (type.startsWith("mail.") ? "https://webmail.irl.coop" : "/apps/chat"),
    urgency: URGENCY[type] ?? "low",
    ts: new Date(row.occurred_at).getTime(),
    read: false,
  };
}
