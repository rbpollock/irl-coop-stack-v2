"use client";

import Link from "next/link";
import { Bell, X } from "lucide-react";

import type { DictionaryType } from "@/lib/get-dictionary";

import { cn, formatDistance, formatUnreadCount } from "@/lib/utils";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardFooter } from "@/components/ui/card";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { DynamicIcon } from "@/components/dynamic-icon";
import {
  useNotifications,
  type LiveNotification,
} from "@/hooks/use-notifications";
import type { DynamicIconNameType } from "@/types";

const ICON_BY_TYPE: Record<string, DynamicIconNameType> = {
  "m.room.message": "MessageSquare",
  "m.room.encrypted": "MessageSquare",
  "m.room.member": "UserPlus",
  "m.reaction": "Heart",
  "m.room.name": "Pencil",
  "m.room.topic": "Pencil",
  "m.room.create": "Plus",
  "mail.received": "Mail",
};

function toRow(n: LiveNotification) {
  return {
    id: n.id,
    iconName: ICON_BY_TYPE[n.type] ?? "Bell",
    content: `${n.title} — ${n.body}`,
    url: n.url || "",
    date: new Date(n.ts),
    isRead: n.read,
  };
}

export function NotificationDropdown({
  dictionary,
}: {
  dictionary: DictionaryType;
}) {
  const { notifications, unread, markAllRead, markRead } = useNotifications();
  const unreadCount = formatUnreadCount(unread);

  return (
    <Popover modal>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="size-4" />
          <span className="sr-only">Notification</span>
          {!!unreadCount && (
            <Badge
              className="absolute -top-1 -end-1 h-4 max-w-8 flex justify-center"
              aria-live="polite"
              aria-atomic="true"
              role="status"
              aria-label={`${unreadCount} unread`}
            >
              {unreadCount}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[380px] p-0">
        <Card className="border-0">
          <div className="flex items-center justify-between border-b border-border p-3">
            <h3 className="text-sm font-semibold">
              {dictionary.navigation.notifications.notifications}
            </h3>
            <Button
              variant="link"
              className="text-primary h-auto p-0"
              onClick={markAllRead}
            >
              {dictionary.navigation.notifications.dismissAll}
            </Button>
          </div>
          <ul>
            {notifications.length === 0 ? (
              <li className="px-6 py-8 text-sm text-muted-foreground text-center">
                No notifications yet
              </li>
            ) : (
              notifications.map((n) => {
                const row = toRow(n);
                return (
                  <li key={row.id}>
                    <div className="group relative flex items-center gap-2 py-4 px-6 hover:bg-accent hover:text-accent-foreground">
                      <Link
                        href={row.url}
                        onClick={() => !row.isRead && markRead([row.id])}
                        className="flex items-center gap-2 flex-1 w-0 min-w-0 focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        <Badge className="h-10 w-10 shrink-0">
                          <DynamicIcon name={row.iconName} className="h-5 w-5" />
                        </Badge>
                        <div className="flex-1 w-0">
                          <p className="text-sm break-all truncate">
                            {row.content}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {formatDistance(row.date)}
                          </p>
                        </div>
                        {!row.isRead && (
                          <div className="h-2 w-2 rounded-full bg-primary shrink-0" />
                        )}
                      </Link>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                        aria-label="Dismiss"
                        onClick={() => markRead([row.id])}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  </li>
                );
              })
            )}
          </ul>
          <CardFooter className="justify-center border-t border-border p-0">
            <Link
              href=""
              className={cn(
                buttonVariants({ variant: "link" }),
                "text-primary text-center"
              )}
            >
              {dictionary.navigation.notifications.seeAllNotifications}
            </Link>
          </CardFooter>
        </Card>
      </PopoverContent>
    </Popover>
  );
}
