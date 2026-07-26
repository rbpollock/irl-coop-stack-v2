import { ContactUs } from "./_components/contact-us"
import { CoreBenefits } from "./_components/core-benefits"
import { CoreFeatures } from "./_components/core-features"
import { Faqs } from "./_components/faqs"
import { Hero } from "./_components/hero"
import { InActionCTA } from "./_components/in-action-cta"
import { PricingPlans } from "./_components/pricing-plans"
import { ReadyToBuildCTA } from "./_components/ready-to-build-cta"
import { TrustedBy } from "./_components/trusted-by"
import { WhatPeopleSay } from "./_components/what-people-say"

export default function LandingPage() {
  return (
    <div className="py-16 space-y-16 bg-muted/40">
      <Hero />
      <TrustedBy />
      <CoreBenefits />
      <WhatPeopleSay />
      <ReadyToBuildCTA />
      <CoreFeatures />
      <InActionCTA />
      <PricingPlans />
      <Faqs />
      <ContactUs />
    </div>
  )
}
