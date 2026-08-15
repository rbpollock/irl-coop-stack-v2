"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable"

export function BasicResizable() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Resizable</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <ResizablePanelGroup direction="horizontal">
          <ResizablePanel>One</ResizablePanel>
          <ResizableHandle />
          <ResizablePanel>Two</ResizablePanel>
        </ResizablePanelGroup>
      </CardContent>
    </Card>
  )
}
