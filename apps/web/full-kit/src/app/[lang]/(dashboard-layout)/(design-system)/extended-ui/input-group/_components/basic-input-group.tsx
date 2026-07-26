import { AtSign, DollarSign, Link2, Lock, Mail, Search } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { InputGroup, InputGroupText } from "@/components/ui/input-group"
import { Textarea } from "@/components/ui/textarea"

export function BasicInputGroup() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Input Group</CardTitle>
      </CardHeader>
      <CardContent className="grid justify-center gap-2">
        <InputGroup>
          <InputGroupText aria-label="@">
            <AtSign className="h-4 w-4" />
          </InputGroupText>
          <Input type="text" placeholder="Username" />
        </InputGroup>
        <InputGroup>
          <Input type="email" placeholder="Email" />
          <InputGroupText>@example.com</InputGroupText>
        </InputGroup>
        <InputGroup>
          <InputGroupText aria-hidden>
            <Search className="h-4 w-4" />
          </InputGroupText>
          <Input type="search" placeholder="Search..." />
          <Button type="submit" variant="secondary">
            Search
          </Button>
        </InputGroup>
        <InputGroup>
          <InputGroupText aria-hidden>
            <Mail className="h-4 w-4" />
          </InputGroupText>
          <Input type="email" placeholder="Email" />
          <InputGroupText aria-hidden>
            <Lock className="h-4 w-4" />
          </InputGroupText>
          <Input type="password" placeholder="Password" />
        </InputGroup>
        <InputGroup>
          <InputGroupText className="items-center" aria-hidden>
            <Mail className="h-4 w-4" />
          </InputGroupText>
          <Textarea placeholder="Type your message here." />
        </InputGroup>
        <InputGroup>
          <InputGroupText aria-hidden>
            <DollarSign className="h-4 w-4" />
          </InputGroupText>
          <Input type="number" placeholder="Amount" min={0} step={1} />
          <InputGroupText>.00</InputGroupText>
        </InputGroup>
        <InputGroup>
          <InputGroupText aria-hidden>
            <Link2 className="h-4 w-4" />
          </InputGroupText>
          <Input type="url" placeholder="your-domain.com" />
          <Button type="button" variant="secondary">
            Verify
          </Button>
        </InputGroup>
      </CardContent>
    </Card>
  )
}
