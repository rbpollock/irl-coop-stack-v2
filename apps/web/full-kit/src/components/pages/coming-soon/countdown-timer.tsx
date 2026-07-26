"use client"

import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"

export function CountdownTimer({ targetDate }: { targetDate: Date }) {
  const [timeLeft, setTimeLeft] = useState({
    days: "00",
    hours: "00",
    minutes: "00",
    seconds: "00",
  })

  // Calculate the time difference and update the state every second
  useEffect(() => {
    const interval = setInterval(() => {
      const now = new Date() // Current date and time
      const difference = targetDate.getTime() - now.getTime() // Calculate the time difference in milliseconds

      // If the target date has not passed
      if (difference > 0) {
        setTimeLeft({
          days: String(Math.floor(difference / (1000 * 60 * 60 * 24))).padStart(
            2, // Ensure at least two digits for display
            "0"
          ),
          hours: String(
            Math.floor((difference / (1000 * 60 * 60)) % 24)
          ).padStart(2, "0"),
          minutes: String(Math.floor((difference / 1000 / 60) % 60)).padStart(
            2,
            "0"
          ),
          seconds: String(Math.floor((difference / 1000) % 60)).padStart(
            2,
            "0"
          ),
        })
      } else {
        // If the countdown has reached or passed the target date, stop the interval
        clearInterval(interval)
      }
    }, 1000)

    // Clean up the interval when the component unmounts or the target date changes
    return () => clearInterval(interval)
  }, [targetDate])

  return (
    <div className="grid grid-cols-4 gap-4">
      {Object.entries(timeLeft).map(([unit, value]) => (
        <Badge key={unit} variant="secondary" className="w-full flex-col p-6">
          <span className="text-3xl font-semibold">{value}</span>
          <span className="capitalize">{unit}</span>
        </Badge>
      ))}
    </div>
  )
}
