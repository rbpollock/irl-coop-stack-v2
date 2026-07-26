import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Iphone15Pro } from "@/components/ui/iphone-15-pro"

export function Iphone15ProMockup() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>iPhone 15 Pro Mockup</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        <Iphone15Pro
          imageSrc="/images/misc/mobile.jpg"
          className="h-96 w-full dark:hidden"
          id="iphone-15-pro-1"
        />
        <Iphone15Pro
          imageSrc="/images/misc/mobile-dark.jpg"
          className="hidden h-96 w-full dark:md:block"
          id="iphone-15-pro-2"
        />
      </CardContent>
    </Card>
  )
}
