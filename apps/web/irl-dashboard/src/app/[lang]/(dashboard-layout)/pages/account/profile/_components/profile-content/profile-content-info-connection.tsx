import Link from "next/link"

import { cn } from "@/lib/utils"

import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ProfileContentConnectionList } from "./profile-content-info-connection-list"

export function ProfileContentConnection() {
  return (
    <Card asChild>
      <article>
        <CardHeader className="flex-row justify-between space-y-0">
          <CardTitle>People you may know</CardTitle>
          <Link
            href="/"
            className={cn(buttonVariants({ variant: "link" }), "size-fit p-0")}
          >
            See All
          </Link>
        </CardHeader>
        <CardContent>
          <ProfileContentConnectionList />
        </CardContent>
      </article>
    </Card>
  )
}
