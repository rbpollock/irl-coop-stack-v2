"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export function BasicSkeleton() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Skeleton</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <div className="flex items-center gap-x-4">
          <Skeleton className="h-12 w-12 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-[250px]" />
            <Skeleton className="h-4 w-[200px]" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
