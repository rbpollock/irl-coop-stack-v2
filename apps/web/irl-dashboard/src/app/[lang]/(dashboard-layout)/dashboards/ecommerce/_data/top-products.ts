import type { TopProductType } from "../types"

export const topProductsData: TopProductType = {
  period: "Last month",
  products: [
    {
      name: "Bluetooth Headphones",
      sku: "BH-001",
      sales: { value: 85, percentageChange: 0.15 },
      revenue: { value: 340000, percentageChange: 0.1 },
      order: 1,
      image: "/images/misc/product-01.jpg",
    },
    {
      name: "Smartwatch",
      sku: "SW-002",
      sales: { value: 72, percentageChange: 0.2 },
      revenue: { value: 576000, percentageChange: 0.12 },
      order: 2,
      image: "/images/misc/product-02.jpg",
    },
    {
      name: "Mirrorless Camera",
      sku: "MC-003",
      sales: { value: 54, percentageChange: -0.05 },
      revenue: { value: 162000, percentageChange: 0.08 },
      order: 3,
      image: "/images/misc/product-03.jpg",
    },
    {
      name: "Smartphone",
      sku: "SP-004",
      sales: { value: 67, percentageChange: 0.1 },
      revenue: { value: 134000, percentageChange: 0.07 },
      order: 4,
      image: "/images/misc/product-04.jpg",
    },
  ],
}
