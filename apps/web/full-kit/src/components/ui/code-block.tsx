"use client"

import { useLayoutEffect, useState } from "react"
import { bundledLanguages } from "shiki/bundle/web"

import type { JSX } from "react"
import type { BundledLanguage } from "shiki/bundle/web"

import { Button } from "@/components/ui/button"
import { highlight } from "../highlight"

function isBundledLanguage(value: unknown): value is BundledLanguage {
  return typeof value === "string" && value in bundledLanguages
}

export function CodeBlock({
  children,
  lang,
}: {
  children: string
  lang: string
}) {
  const [nodes, setNodes] = useState<JSX.Element>()
  const [copied, setCopied] = useState(false)

  const language = isBundledLanguage(lang) ? lang : "markdown"

  useLayoutEffect(() => {
    void highlight(children, language).then(setNodes)
  }, [children, language])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(children)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      console.error("Failed to copy text: ", error)
    }
  }

  return (
    <div className="relative">
      <Button
        variant="secondary"
        className="absolute end-2 top-2 w-16"
        onClick={handleCopy}
      >
        {copied ? "Copied!" : "Copy"}
      </Button>
      {nodes}
    </div>
  )
}
