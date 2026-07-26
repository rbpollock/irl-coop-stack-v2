import {
  Cloud,
  Code,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Zap,
} from "lucide-react"

import {
  BentoContent,
  BentoDescription,
  BentoGrid,
  BentoHeader,
  BentoItem,
  BentoTitle,
} from "@/components/ui/bento-grid"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function BasicBentoGrid() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Bento Grid</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        <BentoGrid>
          <BentoItem className="md:col-span-2">
            <BentoHeader className="flex justify-center items-center">
              <Code className="w-24 h-24 text-primary" />
            </BentoHeader>
            <BentoContent>
              <BentoTitle>Developer Friendly</BentoTitle>
              <BentoDescription>
                Built with modern tools and standards. Get up and running in
                minutes with our easy-to-use SDKs.
              </BentoDescription>
            </BentoContent>
          </BentoItem>
          <BentoItem className="md:row-span-3">
            <BentoHeader className="flex justify-center items-center">
              <ShieldCheck className="w-24 h-24 text-primary" />
            </BentoHeader>
            <BentoContent>
              <BentoTitle>Enterprise Grade Security</BentoTitle>
              <BentoDescription>
                We comply with industry standards like SOC 2 and GDPR to keep
                your data safe and private.
              </BentoDescription>
            </BentoContent>
          </BentoItem>
          <BentoItem>
            <BentoHeader className="flex justify-center items-center">
              <TrendingUp className="w-24 h-24 text-primary" />
            </BentoHeader>
            <BentoContent>
              <BentoTitle>Scalable by Design</BentoTitle>
              <BentoDescription>
                Whether you&apos;re serving 10 users or 10 million, our
                infrastructure grows with your business.
              </BentoDescription>
            </BentoContent>
          </BentoItem>
          <BentoItem>
            <BentoHeader className="flex justify-center items-center">
              <Sparkles className="w-24 h-24 text-primary" />
            </BentoHeader>
            <BentoContent>
              <BentoTitle>Beautiful UI Components</BentoTitle>
              <BentoDescription>
                Fully customizable UI built with Tailwind and Radix — stunning
                out of the box.
              </BentoDescription>
            </BentoContent>
          </BentoItem>
          <BentoItem>
            <BentoHeader className="flex justify-center items-center">
              <Cloud className="w-24 h-24 text-primary" />
            </BentoHeader>
            <BentoContent>
              <BentoTitle>Cloud Native</BentoTitle>
              <BentoDescription>
                Designed for the cloud from day one. Deploy instantly with zero
                configuration.
              </BentoDescription>
            </BentoContent>
          </BentoItem>
          <BentoItem>
            <BentoHeader className="flex justify-center items-center">
              <Zap className="w-24 h-24 text-primary" />
            </BentoHeader>
            <BentoContent>
              <BentoTitle>Blazing Fast</BentoTitle>
              <BentoDescription>
                Optimized for performance. Lightning-fast responses even under
                heavy load.
              </BentoDescription>
            </BentoContent>
          </BentoItem>
        </BentoGrid>
      </CardContent>
    </Card>
  )
}
