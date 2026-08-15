"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable"

export function ResizableVertical() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Resizable Vertical</CardTitle>
      </CardHeader>
      <CardContent className="h-48 flex justify-center items-center">
        <ResizablePanelGroup direction="vertical">
          <ResizablePanel>One</ResizablePanel>
          <ResizableHandle />
          <ResizablePanel>Two</ResizablePanel>
        </ResizablePanelGroup>
      </CardContent>
    </Card>
  )
}
