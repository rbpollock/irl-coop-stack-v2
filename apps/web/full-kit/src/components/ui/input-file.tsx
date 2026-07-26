"use client"

import { useEffect, useImperativeHandle, useRef, useState } from "react"

import type { ChangeEvent, ComponentProps } from "react"

import { cn } from "@/lib/utils"

import { Button } from "@/components/ui/button"

interface InputFileProps
  extends Omit<ComponentProps<"input">, "value" | "onChange"> {
  containerClassName?: string
  buttonVariant?: ComponentProps<typeof Button>["variant"]
  buttonLabel?: string
  placeholder?: string
  value?: FileList
  onValueChange?: (value: FileList) => void
}

export function InputFile({
  className,
  containerClassName,
  buttonVariant,
  buttonLabel,
  placeholder = "No file chosen",
  value,
  onValueChange,
  ...props
}: InputFileProps) {
  const [fileName, setFileName] = useState<string>(placeholder)
  const inputRef = useRef<HTMLInputElement>(null)

  // Forward the ref to the internal ref
  useImperativeHandle(props.ref, () => inputRef.current!)

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files

    if (files) {
      if (files.length > 1) {
        setFileName(`${files.length} Files`)
      } else if (files.length === 1) {
        setFileName(files[0].name)
      } else {
        setFileName(placeholder)
      }

      onValueChange?.(files)
    }
  }

  const handleClick = () => {
    inputRef.current?.click()
  }

  useEffect(() => {
    if (value) {
      if (value.length > 1) {
        setFileName(`${value.length} Files`)
      } else {
        setFileName(value[0].name)
      }
    } else {
      setFileName(placeholder)
    }
  }, [value, placeholder])

  return (
    <div
      data-slot="input-file"
      className={cn(
        "h-9 w-full flex rounded-md border border-input bg-transparent text-sm transition-colors",
        props.disabled && "cursor-not-allowed opacity-50",
        containerClassName
      )}
    >
      <Button
        type="button"
        variant={buttonVariant}
        className="h-full w-28 rounded-e-none border-0 border-e border-input"
        onClick={handleClick}
        disabled={props.disabled}
      >
        {buttonLabel ?? `Choose File${props.multiple ? "s" : ""}`}
      </Button>
      <div className="flex-1 flex items-center text-muted-foreground px-3 break-all">
        <span className="w-0 flex-1 truncate">{fileName}</span>
      </div>
      <input
        {...props}
        ref={inputRef}
        type="file"
        className={cn("hidden", className)}
        onChange={handleFileChange}
      />
    </div>
  )
}
