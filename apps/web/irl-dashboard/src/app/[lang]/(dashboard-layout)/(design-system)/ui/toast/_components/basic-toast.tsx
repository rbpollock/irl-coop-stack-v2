"use client"

import { useToast } from "@/hooks/use-toast"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function BasicToast() {
  const { toast } = useToast()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Toast</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Button
          variant="outline"
          onClick={() => {
            toast({
              description: "Your message has been sent.",
            })
          }}
        >
          Show Toast
        </Button>
      </CardContent>
    </Card>
  )
}
