"use client"

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"

import type { ComponentProps } from "react"
import type { DotProps } from "recharts"
import type { SalesByCountryType } from "../types"

import { camelCaseToTitleCase, formatCurrency } from "@/lib/utils"

import { useIsRtl } from "@/hooks/use-is-rtl"
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
      payload={props.payload.map((item) => ({
        ...item,
        name: camelCaseToTitleCase(String(item.name)),
        value: formatCurrency(Number(item.value)),
      }))}
    />
  )
}

function CustomLineDot({
  cx,
  cy,
  payload,
}: DotProps & { payload: SalesByCountryType["countries"][number] }) {
  const flagUrl = `https://purecatamphetamine.github.io/country-flag-icons/3x2/${payload.countryCode}.svg`
  const size = 24

  return (
    <image
      key={payload.countryName}
      href={flagUrl}
      x={(cx || 0) - size / 2}
      y={(cy || 0) - size / 2}
      width={size}
      height={size}
    />
  )
}

export function SalesByCountryChart({
  data,
}: {
  data: SalesByCountryType["countries"]
}) {
  const isRtl = useIsRtl()

  return (
    <ChartContainer dir="ltr" config={{}} className="aspect-auto h-full w-full">
      <LineChart
        accessibilityLayer
        data={data}
        margin={{
          top: 10,
          bottom: 10,
          left: 10,
          right: 10,
        }}
      >
        <CartesianGrid vertical={false} />
        <YAxis
          orientation={isRtl ? "right" : "left"}
          dataKey="sales"
          tickLine={false}
          axisLine={false}
          tickMargin={20}
          tickFormatter={(value) => formatCurrency(value)}
        />
        <XAxis reversed={isRtl} dataKey="countryName" hide />
        <ChartTooltip
          cursor={false}
          content={<ModifiedChartTooltipContent hideIndicator />}
        />
        <Line
          dataKey="sales"
          type="natural"
          stroke="hsl(var(--border))"
          strokeWidth={2}
          activeDot={false}
          // @ts-ignore
          dot={<CustomLineDot />}
        />
      </LineChart>
    </ChartContainer>
  )
}
