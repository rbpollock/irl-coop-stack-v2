"use client"

import { Bar, BarChart, CartesianGrid, Cell, LabelList, XAxis } from "recharts"

import type { CSSProperties, ComponentProps } from "react"
import type { ChurnRateType } from "../types"

import { camelCaseToTitleCase, formatPercent } from "@/lib/utils"

import { useIsRtl } from "@/hooks/use-is-rtl"
import { useRadius } from "@/hooks/use-radius"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

function ModifiedChartTooltipContent(
  props: ComponentProps<typeof ChartTooltipContent>
) {
  if (!props.payload || props.payload.length === 0) return null

  return (
    <ChartTooltipContent
      {...props}
      formatter={(value, name, item, index) => (
        <>
          <div
            className="shrink-0 h-2.5 w-2.5 rounded-sm bg-(--color-bg)"
            style={
              {
                // @ts-ignore
                "--color-bg": item.fill,
              } as CSSProperties
            }
          />
          {camelCaseToTitleCase(String(name))}
          <div className="flex items-baseline gap-0.5 ms-auto font-mono font-medium tabular-nums text-foreground">
            {value.toLocaleString()}
          </div>
          {/* Add this after the last item */}
          {index === 1 && (
            <div className="flex basis-full items-center border-t mt-1.5 pt-1.5 text-sm font-medium text-foreground">
              Churn Rate
              <div className="flex items-baseline gap-0.5 ms-auto font-mono font-medium tabular-nums text-foreground">
                {formatPercent(item.payload.churnRate)}
              </div>
            </div>
          )}
        </>
      )}
    />
  )
}

export function ChurnRateChart({ data }: { data: ChurnRateType["months"] }) {
  const isRtl = useIsRtl()
  const radius = useRadius()

  return (
    <ChartContainer config={{}} className="aspect-auto grow w-full">
      <BarChart accessibilityLayer data={data} margin={{ top: 20, bottom: 0 }}>
        <CartesianGrid vertical={false} />
        <ChartTooltip
          cursor={false}
          content={<ModifiedChartTooltipContent />}
        />
        <XAxis
          reversed={isRtl}
          dataKey="month"
          tickLine={false}
          axisLine={false}
          tickMargin={10}
          tickFormatter={(value) => value.slice(0, 3)}
        />
        <Bar
          dataKey="totalCustomers"
          stackId="a"
          fill="hsl(var(--chart-2))"
          radius={[0, 0, radius, radius]}
        />

        <Bar
          dataKey="lostCustomers"
          stackId="a"
          fill="hsl(var(--chart-1))"
          radius={[radius, radius, 0, 0]}
        >
          <LabelList
            position="top"
            dataKey="churnRate"
            formatter={(value: number) => formatPercent(value)}
            fontWeight={700}
          />
          {data.map((item) => (
            <Cell key={item.month} fill="hsl(var(--chart-1))" />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}
