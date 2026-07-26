"use client"

import Image from "next/image"

import type { TopProductType } from "../types"

import { formatCurrency } from "@/lib/utils"

import { Card } from "@/components/ui/card"

export function TopProductsItem({
  product,
}: {
  product: TopProductType["products"][0]
}) {
  return (
    <Card className="grid overflow-hidden" asChild>
      <li>
        <div className="flex items-center gap-4 p-2">
          <Image
            src={product.image}
            alt={product.name}
            width={100}
            height={100}
            className="aspect-square h-12 w-12 rounded-lg object-cover"
          />
          <div className="flex flex-col truncate">
            <h3 className="break-all truncate">
              <span>#{product.order}</span>{" "}
              <span className="font-semibold">{product.name}</span>
            </h3>
            <p className="text-sm text-muted-foreground">
              Item: #{product.sku}
            </p>
          </div>
        </div>
        <div className="flex justify-between bg-accent p-2 truncate">
          <p className="text-accent-foreground">
            <span className="text-muted-foreground">Sales: </span>
            <span className="font-semibold">
              {product.sales.value.toLocaleString()}
            </span>
          </p>
          <p className="text-accent-foreground">
            <span className="text-muted-foreground">Revenue: </span>
            <span className="font-semibold">
              {formatCurrency(product.revenue.value)}
            </span>
          </p>
        </div>
      </li>
    </Card>
  )
}
