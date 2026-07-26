import type { IconType } from "@/types"
import type { ReactNode } from "react"
import type { z } from "zod"
import type { ContactUsSchema } from "./_schemas/contact-us-schema"

export type ContactUsType = z.infer<typeof ContactUsSchema>

export interface CoreBenefitType {
  title: string
  description: string
  points: Array<string>
  images: Array<string>
}

export interface CoreFeatureType {
  title: string
  description: string
  icon: IconType
  className?: string
  header?: ReactNode
}

export interface WhatPeopleSayType {
  name: string
  role: string
  company: string
  quote: string
  avatar: string
  rating: number
}

export interface FaqType {
  question: string
  answer: ReactNode
}
