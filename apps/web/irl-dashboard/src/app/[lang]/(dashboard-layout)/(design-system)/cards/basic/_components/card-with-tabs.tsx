import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export function CardWithTabs() {
  return (
    <Card>
      <Tabs defaultValue="home">
        <CardHeader>
          <TabsList>
            <TabsTrigger value="home">Home</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
            <TabsTrigger value="disabled" disabled>
              Disabled
            </TabsTrigger>
          </TabsList>
        </CardHeader>
        <CardContent>
          <TabsContent value="home" className="text-center space-y-3">
            <CardTitle>Welcome to the Homepage</CardTitle>
            <CardDescription>
              Discover the latest updates and explore new features available on
              our platform.
            </CardDescription>
            <Button>Explore</Button>
          </TabsContent>
          <TabsContent value="settings" className="text-center space-y-3">
            <CardTitle>Manage Your Preferences</CardTitle>
            <CardDescription>
              Customize your experience by updating your settings and
              preferences here.
            </CardDescription>
            <Button>Update Settings</Button>
          </TabsContent>
        </CardContent>
      </Tabs>
    </Card>
  )
}
