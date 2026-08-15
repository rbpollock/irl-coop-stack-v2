import Link from "next/link"
import { Bell } from "lucide-react"

import type { DictionaryType } from "@/lib/get-dictionary"

import { notificationData } from "@/data/notifications"

import { cn, formatDistance, formatUnreadCount } from "@/lib/utils"

import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardFooter } from "@/components/ui/card"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { DynamicIcon } from "@/components/dynamic-icon"

export function NotificationDropdown({
  dictionary,
}: {
  dictionary: DictionaryType
}) {
  const unreadCount = formatUnreadCount(notificationData.unreadCount)

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
            <Button variant="link" className="text-primary h-auto p-0">
              {dictionary.navigation.notifications.dismissAll}
            </Button>
          </div>
          <ul>
            {notificationData.notifications.map((notification) => (
              <li key={notification.id}>
                <Link
                  href={notification.url}
                  className="flex items-center gap-2 py-4 px-6 hover:bg-accent hover:text-accent-foreground focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <Badge className="h-10 w-10">
                    <DynamicIcon
                      name={notification.iconName}
                      className="h-5 w-5"
                    />
                  </Badge>
                  <div className="flex-1 w-0">
                    <p className="text-sm break-all truncate">
                      {notification.content}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {formatDistance(notification.date)}
                    </p>
                  </div>
                  {!notification.isRead && (
                    <div className="h-2 w-2 rounded-full bg-primary" />
                  )}
                </Link>
              </li>
            ))}
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
  )
}
