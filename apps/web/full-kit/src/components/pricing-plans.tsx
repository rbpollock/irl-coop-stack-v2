"use client"

import { useRouter } from "next/navigation"
import { Check } from "lucide-react"

import type { ComponentProps, ReactNode } from "react"

import { cn, formatCurrency, getDiscountedPrice } from "@/lib/utils"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export interface PricingPlansType {
  title: string
  description: string
  period?: string
  price?: number
  features: string[]
  isFeatured?: boolean
  isCurrentPlan?: boolean
  buttonOptions?: ComponentProps<typeof Button>
  buttonContent?: ReactNode
  content?: ReactNode
  href: string
}

function RenderPrice({
  price,
  period,
  discountRate,
}: Pick<PricingPlansType, "price" | "period"> & { discountRate?: number }) {
  if (!price) return null

  const finalPrice = discountRate
    ? getDiscountedPrice(price, discountRate, true)
    : price
  const formattedFinalPrice = formatCurrency(finalPrice)

  return (
    <div className="flex justify-center items-baseline mb-8 mt-2">
      <span className="text-4xl font-black">{formattedFinalPrice}</span>
      {period && <span className="text-muted-foreground">/{period}</span>}
    </div>
  )
}

type PricingPlansCardProps = PricingPlansType & { discountRate?: number }

function PricingPlansCard({
  title,
  description,
  price,
  period,
  discountRate,
  features,
  isCurrentPlan = false,
  isFeatured = false,
  buttonOptions,
  buttonContent,
  content,
  href,
}: PricingPlansCardProps) {
  const router = useRouter()

  return (
    <Card
      className={cn(
        "relative h-full flex flex-col",
        isFeatured && "border-primary"
      )}
      asChild
    >
      <li>
        {isFeatured && (
          <Badge className="absolute -top-2.5 start-3 w-fit">Featured</Badge>
        )}
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>
          <RenderPrice
            price={price}
            period={period}
            discountRate={discountRate}
          />
          {content && content}
          {features.length > 0 && (
            <ul className="space-y-2">
              {features.map((feature) => (
                <li key={feature} className="flex items-center gap-x-3">
                  <Check className="size-4 text-success" />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
        <CardFooter className="mt-auto">
          <Button
            size="lg"
            className="w-full"
            disabled={isCurrentPlan}
            onClick={() => router.push(href)}
            {...buttonOptions}
          >
            {buttonContent || (isCurrentPlan ? "Your Current Plan" : "Upgrade")}
          </Button>
        </CardFooter>
      </li>
    </Card>
  )
}

interface PricingPlansProps {
  data: PricingPlansType[]
  discountRate?: number
  className?: string
}

export function PricingPlans({
  data,
  discountRate,
  className,
}: PricingPlansProps) {
  return (
    <ul className={cn("grid gap-4 md:grid-cols-3", className)}>
      {data.map((item) => (
        <PricingPlansCard
          key={item.title}
          discountRate={discountRate}
          {...item}
        />
      ))}
    </ul>
  )
}
