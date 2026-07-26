"use client"

import { useState } from "react"
import { Bar, BarChart, CartesianGrid, XAxis } from "recharts"

import type { ChartConfig } from "@/components/ui/chart"
import type { SalesTrendType } from "../types"

import { cn } from "@/lib/utils"

import { useIsRtl } from "@/hooks/use-is-rtl"
import { useRadius } from "@/hooks/use-radius"
import { Button } from "@/components/ui/button"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

const chartConfig = {
  lead: {
    label: "Lead",
    color: "hsl(var(--chart-1))",
  },
  proposal: {
    label: "Proposal",
    color: "hsl(var(--chart-2))",
  },
  negotiation: {
    label: "Negotiation",
    color: "hsl(var(--chart-3))",
  },
  closed: {
    label: "Closed",
    color: "hsl(var(--chart-4))",
  },
} satisfies ChartConfig

export function SalesTrendChart({ data }: { data: SalesTrendType }) {
  const [activeChart, setActiveChart] =
    useState<keyof typeof chartConfig>("lead")
  const isRtl = useIsRtl()
  const radius = useRadius()

  const { monthly, summary } = data

  return (
    <>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {Object.entries(summary).map(([key, value]) => {
          const stage = key
            .replace("total", "")
            .toLowerCase() as keyof typeof chartConfig

          return (
            <Button
              key={key}
              variant="outline"
              className={cn(
                "size-auto flex-col items-start",
                activeChart === stage && "bg-accent"
              )}
              onClick={() => setActiveChart(stage)}
            >
              <div className="flex items-center gap-x-1">
                <span
                  style={{
                    backgroundColor: chartConfig[stage].color,
                  }}
                  className="h-2.5 w-2.5 rounded-sm"
                />
                <span className="text-sm text-muted-foreground">
                  {chartConfig[stage].label}
                </span>
              </div>
              <span className="text-2xl font-semibold">
                {value.toLocaleString()}
              </span>
            </Button>
          )
        })}
      </div>
      <ChartContainer config={chartConfig} className="grow aspect-auto w-full">
        <BarChart
          accessibilityLayer
          key={activeChart}
          data={monthly}
          margin={{ top: 0, bottom: 0 }}
        >
          <CartesianGrid vertical={false} />
          <XAxis
            reversed={isRtl}
            dataKey="month"
            tickLine={false}
            tickMargin={10}
            axisLine={false}
            tickFormatter={(value) => value.slice(0, 3)}
          />
          <ChartTooltip
            cursor={false}
            content={<ChartTooltipContent indicator="dot" />}
          />
          <Bar
            dataKey={activeChart}
            maxBarSize={44}
            fill={chartConfig[activeChart].color}
            radius={radius}
          />
        </BarChart>
      </ChartContainer>
    </>
  )
}
