"use client"

import { useRef, useState } from "react"
import { Check, ImageIcon, LinkIcon, Palette, Type, Unlink } from "lucide-react"

import type { DynamicIconNameType } from "@/types"
import type { ChainedCommands, Editor } from "@tiptap/react"
import type { FormEvent } from "react"

import { cn } from "@/lib/utils"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { InputFile } from "@/components/ui/input-file"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Separator } from "@/components/ui/separator"
import { Toggle } from "@/components/ui/toggle"
import { DynamicIcon } from "@/components/dynamic-icon"

interface SizeType {
  label: string
  level: 1 | 2 | 3
  textSize: `text-${string}`
}

const sizes: SizeType[] = [
  { label: "Normal", level: 3, textSize: "text-lg" },
  { label: "Large", level: 2, textSize: "text-xl" },
  { label: "Extra Large", level: 1, textSize: "text-2xl" },
]

function SizeHandler({ editor }: { editor: Editor }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          aria-label="Select text style"
        >
          <Type className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="min-w-[8rem] w-auto p-1">
        <div className="flex flex-col">
          <Button
            variant="ghost"
            onClick={() => editor.chain().focus().setParagraph().run()}
            className={cn(
              "justify-start px-3 py-2 text-left text-base",
              editor.isActive("paragraph") && "bg-muted"
            )}
          >
            Small
          </Button>
          {sizes.map((size: SizeType) => (
            <Button
              key={size.level}
              variant="ghost"
              onClick={() =>
                editor
                  .chain()
                  .focus()
                  .toggleHeading({ level: size.level })
                  .run()
              }
              className={cn(
                "justify-start px-3 py-2 text-left",
                size.textSize,
                editor.isActive("heading", { level: size.level }) && "bg-muted"
              )}
            >
              {size.label}
            </Button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}

interface FormatType {
  format: string
  iconName: DynamicIconNameType
}

const formats: FormatType[] = [
  {
    format: "bold",
    iconName: "Bold",
  },
  {
    format: "italic",
    iconName: "Italic",
  },
  {
    format: "underline",
    iconName: "Underline",
  },
  {
    format: "strike",
    iconName: "Strikethrough",
  },
]

function FormatHandler({
  editor,
  format,
  iconName,
}: {
  editor: Editor
  format: string
  iconName: DynamicIconNameType
}) {
  const toggleCommands: Record<string, () => ChainedCommands> = {
    bold: () => editor.chain().focus().toggleBold(),
    italic: () => editor.chain().focus().toggleItalic(),
    underline: () => editor.chain().focus().toggleUnderline(),
    strike: () => editor.chain().focus().toggleStrike(),
  }

  function handlePressChange() {
    const command = toggleCommands[format]

    if (command) {
      command().run()
    }
  }

  return (
    <Toggle
      size="sm"
      pressed={editor.isActive(format)}
      onPressedChange={handlePressChange}
      aria-label={`Toggle ${format} format`}
    >
      <DynamicIcon name={iconName} className="h-4 w-4" />
    </Toggle>
  )
}

interface AlignmentType {
  alignment: string
  iconName: DynamicIconNameType
}

const alignments: AlignmentType[] = [
  { alignment: "left", iconName: "AlignLeft" },
  { alignment: "center", iconName: "AlignCenter" },
  { alignment: "right", iconName: "AlignRight" },
  { alignment: "justify", iconName: "AlignJustify" },
]

function AlignmentHandler({
  editor,
  alignment,
  iconName,
}: {
  editor: Editor
  alignment: string
  iconName: DynamicIconNameType
}) {
  return (
    <Toggle
      size="sm"
      pressed={editor.isActive({ textAlign: alignment })}
      onPressedChange={() =>
        editor.chain().focus().setTextAlign(alignment).run()
      }
      aria-label={`Switch ${alignment} alignment`}
    >
      <DynamicIcon name={iconName} className="h-4 w-4" />
    </Toggle>
  )
}

function ImageHandler({ editor }: { editor: Editor }) {
  const [imageSrc, setImageSrc] = useState<string | null>(null)

  function handleFileChange(files: FileList) {
    if (files.length < 1) return
    const objectURL = URL.createObjectURL(files[0])
    setImageSrc(objectURL)
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (editor && imageSrc) {
      editor.chain().focus().setImage({ src: imageSrc }).run()
      setImageSrc(null)
    }
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          aria-label="Insert image"
        >
          <ImageIcon className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent>
        <form
          onSubmit={(e) => {
            e.stopPropagation()
            handleSubmit(e)
          }}
          className="flex justify-center items-center gap-2"
        >
          <InputFile onValueChange={handleFileChange} />
          <Button
            type="submit"
            variant="ghost"
            size="icon"
            className="shrink-0 h-8 w-8"
            aria-label="Submit"
          >
            <Check className="h-4 w-4" />
          </Button>
        </form>
      </PopoverContent>
    </Popover>
  )
}

function LinkHandler({ editor }: { editor: Editor }) {
  const isLinkActive = editor.isActive("link")

  return isLinkActive ? (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="h-8 w-8"
      onClick={() => editor.chain().focus().unsetLink().run()}
      aria-label="Remove link"
    >
      <Unlink className="h-4 w-4" />
    </Button>
  ) : (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          aria-label="Insert link"
        >
          <LinkIcon className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="flex justify-center items-center gap-2">
        <p className="shrink-0">Insert link</p>
        <Input
          autoFocus
          type="text"
          placeholder="https://www.example.com"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              editor
                .chain()
                .focus()
                .setLink({
                  href: (e.target as HTMLInputElement).value,
                })
                .run()
            }
          }}
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="shrink-0 h-8 w-8"
          onClick={(e) => {
            editor
              .chain()
              .focus()
              .setLink({
                href: (e.target as HTMLInputElement).value,
              })
              .run()
          }}
          aria-label="Submit"
        >
          <Check className="h-4 w-4" />
        </Button>
      </PopoverContent>
    </Popover>
  )
}

function ColorHandler({ editor }: { editor: Editor }) {
  const selectedColor = editor.getAttributes("textStyle").color
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="relative overflow-hidden"
      onClick={() => inputRef.current?.click()}
      aria-label="Select text color"
    >
      <Palette style={{ color: selectedColor }} className="size-4" />
      <Input
        ref={inputRef}
        type="color"
        value={selectedColor}
        onChange={(e) =>
          editor
            .chain()
            .focus()
            .setColor(e.target.value as string)
            .run()
        }
        className="sr-only"
        tabIndex={-1}
      />
    </Button>
  )
}

export function EditorMenuBar({ editor }: { editor: Editor }) {
  return (
    <div
      className="flex flex-wrap items-center gap-1.5 p-1.5"
      aria-label="Editor Menu Bar"
    >
      <SizeHandler editor={editor} />
      <ColorHandler editor={editor} />

      <Separator orientation="vertical" className="h-4" />

      {formats.map(({ format, iconName }) => (
        <FormatHandler
          key={format}
          editor={editor}
          format={format}
          iconName={iconName}
        />
      ))}

      <Separator orientation="vertical" className="h-4" />

      {alignments.map(({ alignment, iconName }) => (
        <AlignmentHandler
          key={alignment}
          editor={editor}
          alignment={alignment}
          iconName={iconName}
        />
      ))}

      <Separator orientation="vertical" className="h-4" />

      <ImageHandler editor={editor} />
      <LinkHandler editor={editor} />
    </div>
  )
}
