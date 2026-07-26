"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export function BasicTabs() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Tabs</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Tabs defaultValue="account" className="w-[400px] grid">
          <TabsList>
            <TabsTrigger value="account">Account</TabsTrigger>
            <TabsTrigger value="password">Password</TabsTrigger>
          </TabsList>
          <TabsContent value="account">
            Make changes to your account here.
          </TabsContent>
          <TabsContent value="password">Change your password here.</TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
