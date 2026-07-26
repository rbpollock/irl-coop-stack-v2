"use client"

import { useToast } from "@/hooks/use-toast"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function ToastWithTitle() {
  const { toast } = useToast()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Toast with Title</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Button
          variant="outline"
          onClick={() => {
            toast({
              title: "Uh oh! Something went wrong.",
              description: "There was a problem with your request.",
            })
          }}
        >
          Show Toast
        </Button>
      </CardContent>
    </Card>
  )
}
