"use client"

import { useToast } from "@/hooks/use-toast"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ToastAction } from "@/components/ui/toast"

export function ToastWithAction() {
  const { toast } = useToast()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Toast with Action</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Button
          variant="outline"
          onClick={() => {
            toast({
              title: "Uh oh! Something went wrong.",
              description: "There was a problem with your request.",
              action: <ToastAction altText="Try again">Try again</ToastAction>,
            })
          }}
        >
          Show Toast
        </Button>
      </CardContent>
    </Card>
  )
}
