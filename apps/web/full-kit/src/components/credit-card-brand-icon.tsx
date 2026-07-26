"use client"

import { CreditCard } from "lucide-react"
import {
  SiAmericanexpress,
  SiDiscover,
  SiMastercard,
  SiVisa,
} from "react-icons/si"

import type { IconProps, IconType } from "@/types"

export const creditCardIcons: Record<string, IconType> = {
  visa: SiVisa,
  mastercard: SiMastercard,
  discover: SiDiscover,
  americanexpress: SiAmericanexpress,
}

interface CreditCardBrandIconProps extends IconProps {
  brandName?: string
}

export function CreditCardBrandIcon({
  brandName,
  ...props
}: CreditCardBrandIconProps) {
  const name = brandName?.toLocaleLowerCase()
  const Icon = creditCardIcons[name as string] || CreditCard

  return <Icon {...props} />
}
