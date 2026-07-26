"use client"

import { faqsData } from "../_data/faqs"

import { Accordion } from "@/components/ui/accordion"
import { Card } from "@/components/ui/card"
import { FaqsItem } from "./faqs-item"

export function FaqsList() {
  return (
    <Card asChild>
      <Accordion type="single" collapsible className="w-full p-6 md:col-span-2">
        {faqsData.map((faq) => (
          <FaqsItem key={faq.question} faq={faq} />
        ))}
      </Accordion>
    </Card>
  )
}
