"use client"

import { Fragment, useCallback, useEffect, useState } from "react"
import { useParams, usePathname, useRouter } from "next/navigation"
import { ChevronDown, Search } from "lucide-react"

import type { DictionaryType } from "@/lib/get-dictionary"
import type {
  LocaleType,
  NavigationNestedItem,
  NavigationRootItem,
} from "@/types"
import type { DialogProps } from "@radix-ui/react-dialog"

import { navigationsData } from "@/data/navigations"

import { ensureLocalizedPathname } from "@/lib/i18n"
import {
  cn,
  getDictionaryValue,
  isActivePathname,
  titleCaseToCamelCase,
} from "@/lib/utils"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { DialogTitle } from "@/components/ui/dialog"
import { Keyboard } from "@/components/ui/keyboard"
import { ScrollArea } from "@/components/ui/scroll-area"
import { DynamicIcon } from "@/components/dynamic-icon"

interface CommandMenuProps extends DialogProps {
  dictionary: DictionaryType
  buttonClassName?: string
}

export function CommandMenu({
  buttonClassName,
  dictionary,
  ...props
}: CommandMenuProps) {
  const [open, setOpen] = useState(false)
  const pathname = usePathname()
  const params = useParams()
  const router = useRouter()

  const locale = params.lang as LocaleType

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || e.key === "/") {
        if (
          (e.target instanceof HTMLElement && e.target.isContentEditable) ||
          e.target instanceof HTMLInputElement ||
          e.target instanceof HTMLTextAreaElement ||
          e.target instanceof HTMLSelectElement
        ) {
          return
        }

        e.preventDefault()
        setOpen((open) => !open)
      }
    }

    document.addEventListener("keydown", down)
    return () => document.removeEventListener("keydown", down)
  }, [])

  const runCommand = useCallback((command: () => unknown) => {
    setOpen(false)
    command()
  }, [])

  const renderMenuItem = (item: NavigationRootItem | NavigationNestedItem) => {
    const title = getDictionaryValue(
      titleCaseToCamelCase(item.title),
      dictionary.navigation
    )
    const label =
      item.label &&
      getDictionaryValue(titleCaseToCamelCase(item.label), dictionary.label)

    // If the item has nested items, render it with a collapsible dropdown.
    if (item.items) {
      return (
        <Collapsible key={item.title} className="group/collapsible">
          <CommandItem asChild>
            <CollapsibleTrigger className="w-full flex justify-between items-center gap-2 px-2 py-1.5 [&[data-state=open]>svg]:rotate-180">
              <span className="flex items-center gap-2">
                {"iconName" in item && (
                  <DynamicIcon name={item.iconName} className="h-4 w-4" />
                )}
                <span>{title}</span>
                {"label" in item && <Badge variant="secondary">{label}</Badge>}
              </span>
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200" />
            </CollapsibleTrigger>
          </CommandItem>
          <CollapsibleContent className="space-y-1 overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
            {item.items.map((subItem: NavigationNestedItem) =>
              renderMenuItem(subItem)
            )}
          </CollapsibleContent>
        </Collapsible>
      )
    }

    // Otherwise, render the item with a link.
    if ("href" in item) {
      const localizedPathname = ensureLocalizedPathname(item.href, locale)
      const isActive = isActivePathname(localizedPathname, pathname)

      return (
        <CommandItem
          key={item.title}
          onSelect={() => runCommand(() => router.push(localizedPathname))}
          className={cn(
            "flex items-center gap-2 px-2 py-1.5",
            isActive && "bg-accent"
          )}
        >
          {"iconName" in item ? (
            <DynamicIcon name={item.iconName} />
          ) : (
            <DynamicIcon name="Circle" />
          )}
          <span>{title}</span>
          {label && <Badge variant="secondary">{label}</Badge>}
        </CommandItem>
      )
    }
  }

  return (
    <>
      <Button
        variant="outline"
        size="lg"
        className={cn(
          "max-w-64 w-full justify-start px-3 rounded-md bg-muted/50 text-muted-foreground",
          buttonClassName
        )}
        onClick={() => setOpen(true)}
        {...props}
      >
        <Search className="me-2 h-4 w-4" />
        <span>{dictionary.search.search}</span>
        <Keyboard className="ms-auto">K</Keyboard>
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen} {...props}>
        <DialogTitle className="sr-only">Search Menu</DialogTitle>
        <CommandInput placeholder={dictionary.search.typeCommand} />
        <CommandList>
          <CommandEmpty>{dictionary.search.noResults}</CommandEmpty>
          <ScrollArea className="h-[300px] max-h-[300px]">
            {navigationsData.map((nav) => {
              const title = getDictionaryValue(
                titleCaseToCamelCase(nav.title),
                dictionary.navigation
              )

              return (
                <CommandGroup
                  key={nav.title}
                  heading={title}
                  className="[&_[cmdk-group-items]]:space-y-1"
                >
                  {nav.items.map((item) => (
                    <Fragment key={item.title}>{renderMenuItem(item)}</Fragment>
                  ))}
                </CommandGroup>
              )
            })}
          </ScrollArea>
        </CommandList>
      </CommandDialog>
    </>
  )
}
