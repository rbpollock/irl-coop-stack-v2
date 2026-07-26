"use client"

import { Label, PolarRadiusAxis, RadialBar, RadialBarChart } from "recharts"

import type { ChartConfig } from "@/components/ui/chart"
import type { LeadSourceType } from "../types"

import { useRadius } from "@/hooks/use-radius"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

const chartConfig = {
  socialMedia: {
    label: "Social Media",
    color: "hsl(var(--chart-1))",
  },
  emailCampaigns: {
    label: "Email Campaigns",
    color: "hsl(var(--chart-2))",
  },
  referrals: {
    label: "Referrals",
    color: "hsl(var(--chart-3))",
  },
  website: {
    label: "Website",
    color: "hsl(var(--chart-4))",
  },
  other: {
    label: "Other",
    color: "hsl(var(--chart-5))",
  },
} satisfies ChartConfig

export function LeadSourcesChart({
  data,
}: {
  data: Pick<LeadSourceType, "leads" | "summary">
}) {
  const radius = useRadius()

  return (
    <ChartContainer
      config={chartConfig}
      className="mx-auto aspect-square flex-1 h-full w-full"
    >
      <RadialBarChart
        accessibilityLayer
        data={[data.leads]}
        innerRadius="85%"
        outerRadius="200%"
      >
        <ChartTooltip
          cursor={false}
          content={<ChartTooltipContent hideLabel />}
        />
        <PolarRadiusAxis tick={false} tickLine={false} axisLine={false}>
          <Label
            content={({ viewBox }) => {
              if (viewBox && "cx" in viewBox && "cy" in viewBox) {
                return (
                  <text
                    x={viewBox.cx}
                    y={viewBox.cy}
                    textAnchor="middle"
                    dominantBaseline="middle"
                  >
                    <tspan
                      x={viewBox.cx}
                      y={viewBox.cy}
                      className="fill-foreground text-2xl font-semibold"
                    >
                      {data.summary.totalLeads.toLocaleString()}
                    </tspan>
                    <tspan
                      x={viewBox.cx}
                      y={(viewBox.cy || 0) + 20}
                      className="text-sm fill-muted-foreground"
                    >
                      Leads
                    </tspan>
                  </text>
                )
              }
            }}
          />
        </PolarRadiusAxis>
        <RadialBar
          dataKey="socialMedia"
          cornerRadius={radius}
          fill="var(--color-socialMedia)"
          className="stroke-transparent stroke-2"
        />
        <RadialBar
          dataKey="emailCampaigns"
          fill="var(--color-emailCampaigns)"
          cornerRadius={radius}
          className="stroke-transparent stroke-2"
        />
        <RadialBar
          dataKey="referrals"
          fill="var(--color-referrals)"
          cornerRadius={radius}
          className="stroke-transparent stroke-2"
        />
        <RadialBar
          dataKey="other"
          fill="var(--color-other)"
          cornerRadius={radius}
          className="stroke-transparent stroke-2"
        />
      </RadialBarChart>
    </ChartContainer>
  )
}
