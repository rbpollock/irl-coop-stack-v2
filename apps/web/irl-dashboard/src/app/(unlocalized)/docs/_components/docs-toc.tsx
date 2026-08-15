"use client"

import { useEffect, useState } from "react"
import { usePathname } from "next/navigation"

import { slugify } from "@/lib/utils"

import { ScrollArea } from "@/components/ui/scroll-area"
import { useSidebar } from "@/components/ui/sidebar"

interface TocItem {
  id: string
  title: string
  level: number
  children?: TocItem[]
}

export function DocsToc() {
  const pathname = usePathname()
  const { isMobile } = useSidebar()
  const [items, setItems] = useState<TocItem[]>([])

  useEffect(() => {
    const content = document.getElementById("mdx-content")
    if (content) {
      const tocItems = generateTree(content, "#mdx-content")
      setItems(tocItems)

      // Apply generated IDs to all headings without IDs
      const headings = content.querySelectorAll("h2, h3, h4")
      headings.forEach((heading, index) => {
        if (!heading.id && tocItems[index]) {
          heading.id = tocItems[index].id
        }
      })
    }
  }, [pathname])

  if (isMobile) {
    return null
  }

  return (
    <aside className="shrink-0 sticky top-[4.25rem] h-svh w-(--sidebar-width) bg-background border-s border-sidebar-border">
      {items.length !== 0 && (
        <nav className="h-[calc(100svh-4rem)]">
          <ScrollArea className="h-full p-4">
            <h2 className="text-sm font-medium mb-4">On this page</h2>
            <Tree items={items} />
          </ScrollArea>
        </nav>
      )}
    </aside>
  )
}

function Tree({ items }: { items: TocItem[] }) {
  const [activeId, setActiveId] = useState<string>("")

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id)
          }
        })
      },
      { rootMargin: "0px 0px -60% 0px" }
    )

    const headers = document.querySelectorAll(
      "#mdx-content h2, #mdx-content h3, #mdx-content h4"
    )
    headers.forEach((header) => observer.observe(header))

    return () => {
      headers.forEach((header) => observer.unobserve(header))
      setActiveId("")
    }
  }, [items])

  const renderItems = (items: TocItem[]) => {
    return (
      <ul className="space-y-2 text-sm">
        {items.map((item) => (
          <li key={item.id}>
            <a
              href={`#${item.id}`}
              className={`block py-1 ${
                activeId === item.id
                  ? "text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {item.title}
            </a>
            {item.children && item.children.length > 0 && (
              <div className="ms-4 mt-2 space-y-2 text-sm">
                {renderItems(item.children)}
              </div>
            )}
          </li>
        ))}
      </ul>
    )
  }

  return renderItems(items)
}

function generateTree(content: HTMLElement, selector: string): TocItem[] {
  const headings = Array.from(
    content.querySelectorAll(`${selector} h2, ${selector} h3, ${selector} h4`)
  )
  const tree: TocItem[] = []
  const stack: TocItem[] = []
  const usedIds = new Set<string>()

  headings.forEach((heading) => {
    const level = parseInt(heading.tagName.charAt(1), 10)
    const title = heading.textContent?.trim() || ""
    const id = heading.id || slugify(title)

    // Ensure unique ID
    let uniqueId = id
    let counter = 1
    while (usedIds.has(uniqueId)) {
      uniqueId = `${id}-${counter}`
      counter++
    }
    usedIds.add(uniqueId)

    // Assign unique ID back to the heading (optional but helpful)
    heading.id = uniqueId

    const item: TocItem = { id: uniqueId, title, level, children: [] }

    // Maintain hierarchy using stack
    while (stack.length > 0 && stack[stack.length - 1].level >= item.level) {
      stack.pop()
    }

    if (stack.length > 0) {
      stack[stack.length - 1].children?.push(item)
    } else {
      tree.push(item)
    }

    stack.push(item)
  })

  return tree
}
