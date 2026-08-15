import { clsx } from "clsx"
import { format, formatDistanceToNow, intervalToDuration } from "date-fns"
import { twMerge } from "tailwind-merge"
import { z } from "zod"

import type { FormatStyleType, LocaleType } from "@/types"
import type { ClassValue } from "clsx"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function getInitials(fullName: string) {
  if (fullName.length === 0) return ""

  // Split the name by spaces
  const names = fullName.split(" ")
  // Extract the first letter of each name and convert it to uppercase
  const initials = names.map((name) => name.charAt(0).toUpperCase()).join("")

  return initials
}

export const isEven = (num: number) => num % 2 === 0

export function getCreditCardBrandName(number: string) {
  const re = {
    visa: /^4/,
    mastercard: /^5[1-5]/,
    amex: /^3[47]/,
    discover: /^6(?:011|5)/,
  }

  for (const [type, regex] of Object.entries(re)) {
    if (regex.test(number)) return type
  }
  return "unknown"
}

export function remToPx(rem: number) {
  // Get the root font size (default is 16px if not set otherwise)
  const rootFontSize = parseFloat(
    getComputedStyle(document.documentElement).fontSize
  )
  return rem * rootFontSize
}

export function isUrl(text: string) {
  return z.string().url().safeParse(text).success
}

export function isActivePathname(
  basePathname: string,
  currentPathname: string,
  exactMatch: boolean = false
) {
  if (typeof basePathname !== "string" || typeof currentPathname !== "string") {
    throw new Error("Both basePathname and currentPathname must be strings")
  }

  // Use this when you want a strict comparison, e.g., highlighting a specific page.
  if (exactMatch) {
    return basePathname === currentPathname
  }

  // Allow deeper routes to be considered as active.
  // Example: If basePathname is "/dashboard", it should match "/dashboard/stats".
  return (
    currentPathname.startsWith(basePathname) &&
    (currentPathname.length === basePathname.length ||
      currentPathname[basePathname.length] === "/")
  )
}

export function formatFileSize(bytes: number, decimals: number = 2) {
  if (bytes === 0) return "0 Bytes"

  const k = 1000 // Use 1024 for binary
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ["Bytes", "KB", "MB", "GB", "TB", "PB"]

  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i]
}

export function formatFileType(type: string) {
  return type.slice(0, type.lastIndexOf("/"))
}

export function ratingToPercentage(
  rating: number,
  maxRating: number,
  fractionDigits: number = 0
) {
  const value = ((rating / maxRating) * 100).toFixed(fractionDigits)
  const result = value + "%"

  return result
}

export function formatCurrency(
  value: number,
  locales: LocaleType = "en",
  currency: string = "USD"
) {
  return new Intl.NumberFormat(locales, {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value)
}

export function formatPercent(value: number, locales: LocaleType = "en") {
  return new Intl.NumberFormat(locales, {
    style: "percent",
    maximumFractionDigits: 0,
  }).format(value)
}

export function formatDate(value: string | number | Date) {
  return format(value, "PP")
}

export function formatRelativeDate(value?: string | number | Date) {
  if (!value) return "No Date"

  const date = new Date(value)
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(today.getDate() - 1)

  if (date.toDateString() === today.toDateString()) return "Today"
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday"

  return formatDate(value)
}

export function formatDateWithTime(value: string | number | Date) {
  return format(value, "PP hh:mm a")
}

export function formatDateShort(value: string | number | Date) {
  return format(value, "MMM dd")
}

export function formatTime(value: string | number | Date) {
  return format(value, "h:mm a")
}

export function formatDuration(value: string | number | Date) {
  const numberValue = Number(value)
  const isNegative = numberValue < 0
  const absoluteValue = Math.abs(numberValue)

  const duration = intervalToDuration({ start: 0, end: absoluteValue })

  const hours = duration.hours ? `${duration.hours}h` : ""
  const minutes = duration.minutes ? `${duration.minutes}m` : ""
  const seconds = duration.seconds ? `${duration.seconds}s` : ""

  const formattedDuration = `${hours} ${minutes} ${seconds}`.trim()

  return isNegative ? `-${formattedDuration}` : formattedDuration
}

export function formatDistance(value: string | number | Date) {
  const distance = formatDistanceToNow(value, { addSuffix: true })

  const replacements: Record<string, string> = {
    minute: "min",
    minutes: "mins",
    hour: "hr",
    hours: "hrs",
    day: "day",
    days: "days",
    month: "month",
    months: "months",
    year: "year",
    years: "years",
  }

  if (distance === "less than a minute ago") {
    return "just now"
  }

  // Replace phrases based on the mapping
  return distance
    .replace(
      /less than a minute|minute|minutes|hour|hours|day|days|month|months|year|years/g,
      (match) => replacements[match]
    )
    .replace(/\b(over|almost|about)\b/g, "")
}

export function formatNumberToCompact(
  value: number,
  locales: LocaleType = "en"
) {
  return new Intl.NumberFormat(locales, {
    notation: "compact",
    compactDisplay: "short",
  }).format(value)
}

export function timeToDate(timeString: string, baseDate = new Date()) {
  if (!/^\d{2}:\d{2}$/.test(timeString)) {
    throw new Error("Invalid time format. Use 'HH:mm'.")
  }

  const [hours, minutes] = timeString.split(":").map(Number)
  const date = new Date(baseDate) // Clone base date

  date.setHours(hours, minutes, 0, 0) // Set hours and minutes, reset seconds & milliseconds

  return date
}

export function camelCaseToTitleCase(camelCaseStr: string) {
  const titleCaseStr = camelCaseStr
    .replace(/([A-Z])/g, " $1") // Insert space before uppercase letters
    .replace(/^./, (char) => char.toUpperCase()) // Capitalize the first letter

  return titleCaseStr
}

export function titleCaseToCamelCase(titleCaseStr: string) {
  const camelCaseStr = titleCaseStr
    .toLowerCase() // Convert the entire string to lowercase first
    .replace(/\s+(.)/g, (_, char) => char.toUpperCase()) // Remove spaces and capitalize the following character

  return camelCaseStr
}

export function slugify(text: string) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-") // Replace non-alphanumeric chars with "-"
    .replace(/^-+|-+$/g, "") // Remove leading/trailing dashes
}

export function ensureWithPrefix(value: string, prefix: string) {
  return value.startsWith(prefix) ? value : `${prefix}${value}`
}

export function ensureWithSuffix(value: string, suffix: string) {
  return value.endsWith(suffix) ? value : `${value}${suffix}`
}

export function ensureWithoutSuffix(value: string, suffix: string) {
  return value.endsWith(suffix) ? value.slice(0, -suffix.length) : value
}

export function ensureWithoutPrefix(value: string, prefix: string) {
  return value.startsWith(prefix) ? value.slice(prefix.length) : value
}

export function ensureRedirectPathname(
  basePathname: string,
  redirectPathname: string
) {
  const searchParams = new URLSearchParams({
    redirectTo: ensureWithoutSuffix(redirectPathname, "/"),
  })

  return ensureWithSuffix(basePathname, "?" + searchParams.toString())
}

export function isNonNegative(num: number) {
  return num >= 0
}

export function getDiscountedPrice(
  price: number,
  discountRate: number,
  isAnnual: boolean = false
) {
  if (isAnnual) {
    // Apply discount to the annual price
    const annualPrice = price * 12
    const discountedAnnualPrice = annualPrice * (1 - discountRate)

    // Calculate the equivalent monthly price after the discount
    const monthlyEquivalentPrice = discountedAnnualPrice / 12
    return monthlyEquivalentPrice
  } else {
    // Apply discount directly to the monthly price
    const discountedMonthlyPrice = price * (1 - discountRate)
    return discountedMonthlyPrice
  }
}

export function isBeforeToday(date: Date) {
  // Get the start of today
  const startOfToday = new Date(new Date().setHours(0, 0, 0, 0))

  // Compare the dates
  return date < startOfToday
}

export function formatUnreadCount(unreadCount: number) {
  // If the unread count is 100 or more, display "+99"; otherwise, display the actual unread count.
  return unreadCount >= 100 ? "+99" : unreadCount
}

export function wait(ms: number = 250) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function formatOverviewCardValue(
  value: number,
  formatStyle: FormatStyleType
): string | number {
  switch (formatStyle) {
    case "percent":
      return formatPercent(value)
    case "duration":
      return formatDuration(value)
    case "currency":
      return formatCurrency(value)
    default:
      return value.toLocaleString("en", {
        maximumFractionDigits: 0,
      })
  }
}

// Retrieve the dictionary value safely
export function getDictionaryValue(
  key: string,
  section: Record<string, unknown>
) {
  const value = section[key]

  if (typeof value !== "string") {
    throw new Error(
      `Invalid dictionary value for key: ${key}. Please ensure all values are correctly set in the dictionary files.`
    )
  }

  return value
}
