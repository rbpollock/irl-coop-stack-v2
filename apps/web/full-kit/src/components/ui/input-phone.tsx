"use client"

import { useCallback, useMemo } from "react"
import Image from "next/image"
import { useDirection } from "@radix-ui/react-direction"
import * as RPNInputPrimitive from "react-phone-number-input"
import { Check, ChevronsUpDown } from "lucide-react"

import type { ComponentProps, ComponentPropsWithoutRef } from "react"

import { cn } from "@/lib/utils"

import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { Input } from "@/components/ui/input"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { ScrollArea } from "./scroll-area"

type InputPhoneProps = Omit<
  ComponentPropsWithoutRef<"input">,
  "onChange" | "value"
> &
  Omit<
    RPNInputPrimitive.Props<typeof RPNInputPrimitive.default>,
    "onChange"
  > & {
    onChange?: (value: RPNInputPrimitive.Value) => void
  }

export function InputPhone({ className, onChange, ...props }: InputPhoneProps) {
  const direction = useDirection()

  return (
    <RPNInputPrimitive.default
      data-slot="input-phone"
      dir={direction}
      className={cn("w-full flex", className)}
      flagComponent={FlagComponent}
      countrySelectComponent={CountrySelect}
      inputComponent={InputComponent}
      /**
       * Handles the onChange event.
       *
       * react-phone-number-input might trigger the onChange event as undefined
       * when a valid phone number is not entered. To prevent this,
       * the value is coerced to an empty string.
       *
       * @param {E164Number | undefined} value - The entered value
       */
      onChange={(value) => onChange?.(value as RPNInputPrimitive.Value)}
      {...props}
    />
  )
}

function InputComponent({ className, ...props }: ComponentProps<"input">) {
  return (
    <Input
      className={cn("rounded-e-md rounded-s-none", className)}
      {...props}
    />
  )
}

interface CountrySelectOption {
  label: string
  value: RPNInputPrimitive.Country
}

interface CountrySelectProps {
  disabled?: boolean
  value: RPNInputPrimitive.Country
  onChange: (value: RPNInputPrimitive.Country) => void
  options: CountrySelectOption[]
}

function CountrySelect({
  disabled,
  value,
  onChange,
  options,
}: CountrySelectProps) {
  const handleSelect = useCallback(
    (country: RPNInputPrimitive.Country) => onChange(country),
    [onChange]
  )

  const memoizedOptions = useMemo(
    () =>
      options.map((option) => (
        <CommandItem
          className="flex gap-2 w-full"
          key={option.value || "ZZ"}
          onSelect={() => handleSelect(option.value)}
        >
          <FlagComponent country={option.value} countryName={option.label} />
          <span className="flex-1 text-sm">{option.label}</span>
          {option.value && (
            <span className="text-foreground/50 text-sm">
              {`+${RPNInputPrimitive.getCountryCallingCode(option.value)}`}
            </span>
          )}
          <span aria-label={option.value === value ? "Selected" : undefined}>
            <Check
              className={cn(
                "ms-auto size-4",
                option.value === value ? "opacity-100" : "opacity-0"
              )}
            />
          </span>
        </CommandItem>
      )),
    [options, handleSelect, value]
  )

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          className={cn("flex gap-1 rounded-e-none rounded-s-lg px-3")}
          disabled={disabled}
        >
          <FlagComponent country={value} countryName={value} />
          <ChevronsUpDown
            className={cn(
              "-me-2 size-4 opacity-50",
              disabled ? "hidden" : "opacity-100"
            )}
            aria-hidden
          />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[300px] p-0" align="start">
        <Command>
          <CommandInput placeholder="Search country..." />
          <CommandList>
            <CommandEmpty>No country found.</CommandEmpty>
            <ScrollArea className="h-[300px] max-h-[300px]">
              <CommandGroup>{memoizedOptions}</CommandGroup>
            </ScrollArea>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

function FlagComponent({ country, countryName }: RPNInputPrimitive.FlagProps) {
  const flagUrl = `https://purecatamphetamine.github.io/country-flag-icons/3x2/${country}.svg`

  return (
    <div className="relative h-4 w-6 bg-foreground/20 rounded-sm">
      {country && (
        <Image
          src={flagUrl}
          alt={countryName}
          fill
          className="rounded-sm object-cover"
        />
      )}
    </div>
  )
}
