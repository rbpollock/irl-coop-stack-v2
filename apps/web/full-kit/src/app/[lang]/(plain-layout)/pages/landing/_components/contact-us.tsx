import { ContactUsForm } from "./contact-us-form"
import { ContactUsInfo } from "./contact-us-info"

export function ContactUs() {
  return (
    <section
      id="contact-us"
      className="container grid gap-4 md:grid-cols-3 md:gap-8"
    >
      <div className="space-y-8 md:space-y-4">
        <div className="text-center space-y-1.5 md:text-start">
          <h2 className="text-4xl font-semibold">Contact Us</h2>
          <p className="max-w-prose mx-auto text-sm text-muted-foreground">
            Have a question or need assistance? Fill out the form, and
            we&apos;ll get back to you as soon as possible.
          </p>
        </div>
        <ContactUsInfo />
      </div>
      <ContactUsForm />
    </section>
  )
}
