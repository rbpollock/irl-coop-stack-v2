"use client"

import { usePathname } from "next/navigation"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"

export function DocsBreadcrumb() {
  const pathname = usePathname()
  const paths = pathname.split("/").filter(Boolean)
  const pathsOfDocs = paths.slice(2)

  if (!paths[1]) return

  return (
    <Breadcrumb>
      <BreadcrumbList>
        <BreadcrumbItem>
          <BreadcrumbLink href="/docs">Home</BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbSeparator />
        <BreadcrumbItem className="capitalize">
          {paths[1].replace("-", " ").toLowerCase()}
        </BreadcrumbItem>
        <BreadcrumbSeparator />
        {pathsOfDocs.map((segment, index) => {
          const href = "/" + pathsOfDocs.slice(0, index + 1).join("/")
          const label = segment.replace("-", " ").toLowerCase()

          return (
            <BreadcrumbItem key={href}>
              {index === pathsOfDocs.length - 1 ? (
                <BreadcrumbPage className="capitalize">{label}</BreadcrumbPage>
              ) : (
                <>
                  <BreadcrumbLink href={href} className="capitalize">
                    {label}
                  </BreadcrumbLink>
                  <BreadcrumbSeparator />
                </>
              )}
            </BreadcrumbItem>
          )
        })}
      </BreadcrumbList>
    </Breadcrumb>
  )
}
