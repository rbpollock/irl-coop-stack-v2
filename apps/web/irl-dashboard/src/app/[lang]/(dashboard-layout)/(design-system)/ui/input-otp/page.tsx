import type { Metadata } from "next"

import { BasicInputOtp } from "./_components/basic-input-otp"
import { InputOtpPattern } from "./_components/input-otp-pattern"
import { InputOtpSeparator } from "./_components/input-otp-separator"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Input OTP",
}

export default function InputOtpPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicInputOtp />
      <InputOtpPattern />
      <InputOtpSeparator />
    </section>
  )
}
