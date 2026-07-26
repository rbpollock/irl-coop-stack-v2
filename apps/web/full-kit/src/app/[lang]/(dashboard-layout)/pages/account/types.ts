import type { MediaType } from "@/components/ui/media-grid"
import type { DynamicIconNameType } from "@/types"
import type { z } from "zod"
import type { DeleteAccountSchema } from "./settings/_schemas/delete-account-schema"
import type { ProfileInfoSchema } from "./settings/_schemas/profile-info-form-schema"
import type { NotificationPreferencesSchema } from "./settings/notifications/_schemas/notifications-preferenes-schema"
import type { ChangePlanSchema } from "./settings/plan-and-billing/_schemas/change-plan-schema"
import type { PaymentMethodSchema } from "./settings/plan-and-billing/_schemas/payment-method-schema"
import type { AccountRecoveryOptionsSchema } from "./settings/security/_schemas/account-recovery-options-schema"
import type { ChangePasswordSchema } from "./settings/security/_schemas/chnage-password-schema"
import type { SecurityPreferencesSchema } from "./settings/security/_schemas/security-preferences-form-schema"

export interface UserType {
  id: string
  firstName: string
  lastName: string
  name: string
  password: string
  username: string
  role: string
  avatar: string
  background: string
  status: string
  phoneNumber: string
  email: string
  state: string
  country: string
  address: string
  zipCode: string
  language: string
  timeZone: string
  currency: string
  organization: string
  twoFactorAuth: boolean
  loginAlerts: boolean
  accountReoveryOption?: "email" | "sms" | "codes"
  connections: number
  followers: number
}

export interface PlanType {
  id: number
  name: string
  price: number
  features: string[]
}

export interface SubscriptionType {
  id: number
  planId: number
  interval: "monthly" | "yearly"
  startDate: string
  endDate: string
  status: "active" | "expired" | "canceled"
  createdAt?: string
  updatedAt?: string
}

export interface CurrentPlanType {
  plan: {
    name: string
    price: string
    description: string
  }
  stats: {
    activeProjects: {
      value: number
      max: number
      progress: number
    }
    teamMembers: {
      value: number
      max: number
      progress: number
    }
    storageUsed: {
      value: number
      max: number
      progress: number
    }
  }
  activityThisMonth: Array<{
    iconName: DynamicIconNameType
    count: number
    label: string
  }>
  billingInfo: {
    nextBillingDate: Date
    amountDue: number
  }
}

export type DeleteAccountFormType = z.infer<typeof DeleteAccountSchema>

export type ProfileInfoFormType = z.infer<typeof ProfileInfoSchema>

export type NotificationPreferencesFormType = z.infer<
  typeof NotificationPreferencesSchema
>

export type ChangePlanFormType = z.infer<typeof ChangePlanSchema>

export type PaymentMethodFormType = z.infer<typeof PaymentMethodSchema>

export type AccountRecoveryOptionsFormType = z.infer<
  typeof AccountRecoveryOptionsSchema
>

export type ChangePasswordFormType = z.infer<typeof ChangePasswordSchema>

export type SecurityPreferencesFormType = z.infer<
  typeof SecurityPreferencesSchema
>

export type VisibilityType = "public" | "friends" | "private"

export type UserPostType = Pick<UserType, "name" | "avatar">

export interface PostType {
  id: string
  user: UserPostType
  updatedAt: Date
  text: string
  totalComments: number
  totalReposts: number
  totalLikes: number
  media?: Array<MediaType>
  visibility: VisibilityType
  isLiked: boolean
}

export type UserProfileConnectionType = Pick<
  UserType,
  "name" | "avatar" | "connections"
>
