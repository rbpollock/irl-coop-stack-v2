import { SocialMediaLinks } from "@/components/social-media-links"
import { ComingSoonForm } from "./coming-soon-form"
import { CountdownTimer } from "./countdown-timer"

export function ComingSoon({ targetDate }: { targetDate: Date }) {
  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center gap-y-6 text-center text-foreground bg-background p-4">
      <h1 className="text-6xl text-primary font-black">Coming Soon</h1>
      <p className="text-xl text-muted-foreground">
        We&apos;re working hard to bring you something amazing. Stay tuned!
      </p>
      <CountdownTimer targetDate={targetDate} />
      <ComingSoonForm />
      <SocialMediaLinks />
    </div>
  )
}
