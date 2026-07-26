import type { Metadata } from "next"

import { paymentData } from "./_data/payment"

import { CardTitle } from "@/components/ui/card"
import { PaymentContent } from "./_components/payment-contnet"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Payment",
}

export default function PaymentPage() {
  return (
    <section className="container p-4">
      <CardTitle className="pb-6">Payment</CardTitle>
      <PaymentContent data={paymentData} />
    </section>
  )
}
