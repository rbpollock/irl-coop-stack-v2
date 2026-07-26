import Image from "next/image"

import type { MDXComponents } from "mdx/types"
import type { ImageProps } from "next/image"

import { CodeBlock } from "./components/ui/code-block"

// This file allows you to provide custom React components
// to be used in MDX files. You can import and use any
// React component you want, including inline styles,
// components from other libraries, and more.

export function useMDXComponents(components: MDXComponents): MDXComponents {
  return {
    // Allows customizing built-in components, e.g. to add styling.
    h1: ({ children }) => <h1 className="text-xl font-bold">{children}</h1>,
    h2: ({ children }) => (
      <h2 className="text-lg font-bold text-muted-foreground -mt-2">
        {children}
      </h2>
    ),
    img: (props) => (
      // eslint-disable-next-line jsx-a11y/alt-text
      <Image
        sizes="100vw"
        style={{ width: "100%", height: "auto" }}
        {...(props as ImageProps)}
      />
    ),
    code: ({ children, className }) => {
      if (className) {
        const lang = className?.replace(/language-/, "") || "markdown"
        return <CodeBlock lang={lang}>{children as string}</CodeBlock>
      }
      return (
        <code className="px-3 py-1 bg-primary/5 text-foreground rounded-md before:content-none after:content-none">
          {children}
        </code>
      )
    },
    pre: ({ children }) => <>{children}</>,
    ...components,
  }
}
