"use client"

import type { TopProductType } from "../types"

import { TopProductsItem } from "./top-products-item"

export function TopProductsList({
  data,
}: {
  data: TopProductType["products"]
}) {
  return (
    <ul className="space-y-2">
      {data.map((product) => (
        <TopProductsItem key={product.sku} product={product} />
      ))}
    </ul>
  )
}
