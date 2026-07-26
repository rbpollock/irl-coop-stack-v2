"use client"

import { useEffect, useState } from "react"
import { Minus, Plus } from "lucide-react"

import type { ChangeEvent, ComponentProps } from "react"

import { cn } from "@/lib/utils"

import { Button } from "@/components/ui/button"

interface InputSpinProps
  extends Omit<
    ComponentProps<"input">,
    "onChange" | "value" | "min" | "max" | "step"
  > {
  value?: number
  onChange?: (value: number) => void
  min?: number
  max?: number
  step?: number
  buttonVariant?: ComponentProps<typeof Button>["variant"]
}

export function InputSpin({
  value,
  onChange,
  min = -Infinity,
  max = Infinity,
  step = 1,
  disabled = false,
  className,
  buttonVariant = "default",
  ...props
}: InputSpinProps) {
  const [internalValue, setInternalValue] = useState<number>(value ?? 0)

  function handleIncrement() {
    const newValue = internalValue + step
    if (newValue <= max) {
      setInternalValue(newValue)
      onChange?.(newValue)
    }
  }

  function handleDecrement() {
    const newValue = internalValue - step
    if (newValue >= min) {
      setInternalValue(newValue)
      onChange?.(newValue)
    }
  }

  const handleOnChange = (e: ChangeEvent<HTMLInputElement>) => {
    const newValue = parseFloat(e.target.value)
    if (!isNaN(newValue) && newValue >= min && newValue <= max) {
      setInternalValue(newValue)
      onChange?.(newValue)
    }
  }

  useEffect(() => {
    if (value !== undefined) {
      setInternalValue(value)
    }
  }, [value])

  return (
    <div
      data-slot="input-spin"
      className={cn(
        "h-9 w-fit flex justify-between items-center p-0.5 rounded-md border border-input bg-transparent text-sm transition-colors",
        disabled && "cursor-not-allowed opacity-50",
        className
      )}
    >
      <Button
        type="button"
        variant={buttonVariant}
        size="icon"
        className="h-full w-auto aspect-square"
        onClick={handleDecrement}
        disabled={disabled || internalValue <= min}
        aria-label="Decrease value"
      >
        <Minus className="h-4 w-4" />
      </Button>
      <input
        type="number"
        value={internalValue}
        className={cn(
          "h-full w-10 border-0 bg-transparent text-sm text-center focus:outline-hidden focus:ring-0",
          "[-moz-appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
        )}
        onChange={handleOnChange}
        disabled={disabled}
        min={min}
        max={max}
        step={step}
        readOnly
        {...props}
      />
      <Button
        type="button"
        variant={buttonVariant}
        size="icon"
        className="h-full w-auto aspect-square"
        onClick={handleIncrement}
        disabled={disabled || internalValue >= max}
        aria-label="Increase value"
      >
        <Plus className="h-4 w-4" />
      </Button>
    </div>
  )
}
