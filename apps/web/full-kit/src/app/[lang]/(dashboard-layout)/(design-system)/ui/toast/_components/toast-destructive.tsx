"use client"

import { useToast } from "@/hooks/use-toast"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ToastAction } from "@/components/ui/toast"

export function ToastDestructive() {
  const { toast } = useToast()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Toast Destructive</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Button
          variant="outline"
          onClick={() => {
            toast({
              variant: "destructive",
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
