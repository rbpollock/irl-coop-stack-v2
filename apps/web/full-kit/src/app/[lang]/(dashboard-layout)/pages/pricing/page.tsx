import type { Metadata } from "next"

import { pricingData } from "./_data/pricing"

import { Pricing } from "./_components/pricing"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Pricing",
}

export default function PricingPage() {
  return (
    <section className="container grid gap-8 p-4">
      <div className="mx-auto text-center space-y-1.5">
        <h2 className="text-4xl font-semibold">Flexible Pricing Plans</h2>
        <p className="max-w-prose text-sm text-muted-foreground">
          Choose from our flexible pricing plans to find the perfect fit for
          your needs. and capital can unlock long-term value and drive economic
          growth.
        </p>
      </div>
      <Pricing data={pricingData} />
    </section>
  )
}
