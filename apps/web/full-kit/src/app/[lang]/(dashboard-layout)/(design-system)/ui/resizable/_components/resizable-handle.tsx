"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable"

export function ResizableHandleComponent() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Resizable Handle</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <ResizablePanelGroup direction="horizontal">
          <ResizablePanel>One</ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel>Two</ResizablePanel>
        </ResizablePanelGroup>
      </CardContent>
    </Card>
  )
}
