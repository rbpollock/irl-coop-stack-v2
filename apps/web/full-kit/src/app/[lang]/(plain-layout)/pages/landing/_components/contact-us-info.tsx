import { contactUsInfoData } from "../_data/contact-us-info"

import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"

export function ContactUsInfo() {
  return (
    <ul className="flex flex-col gap-y-4">
      {contactUsInfoData.map((item) => (
        <Card key={item.title} asChild>
          <li className="flex items-center gap-x-2 p-6 text-start">
            <Badge className="size-12 aspect-square" aria-hidden>
              <item.icon className="size-full" />
            </Badge>
            <div className="flex-1">
              <h3 className="text-sm text-muted-foreground leading-tight">
                {item.title}
              </h3>
              <p className="font-semibold break-all">{item.value}</p>
            </div>
          </li>
        </Card>
      ))}
    </ul>
  )
}
