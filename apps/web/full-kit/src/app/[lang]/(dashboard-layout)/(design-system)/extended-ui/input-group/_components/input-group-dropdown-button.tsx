"use client"

import { ChevronDown } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { InputGroup } from "@/components/ui/input-group"

export function InputGroupDropdownAndButton() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Input Dropdown and Button</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        <InputGroup>
          <Input type="text" />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="secondary">
                Dropdown <ChevronDown className="ms-2 h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem>Action 1</DropdownMenuItem>
              <DropdownMenuItem>Action 2</DropdownMenuItem>
              <DropdownMenuItem>Action 3</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </InputGroup>
        <InputGroup>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="secondary">
                Dropdown <ChevronDown className="ms-2 h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem>Action 1</DropdownMenuItem>
              <DropdownMenuItem>Action 2</DropdownMenuItem>
              <DropdownMenuItem>Action 3</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Input type="text" />
        </InputGroup>
        <InputGroup>
          <Button variant="secondary">Button</Button>
          <Input type="text" />
        </InputGroup>
        <InputGroup>
          <Input type="text" />
          <Button variant="secondary">Button</Button>
        </InputGroup>
      </CardContent>
    </Card>
  )
}
