declare module "*.mdx" {
  import type { FC } from "react"

  export const metadata: {
    title: string
    description: string
    date: string
    [key: string]: number | string
  }

  const MDXComponent: FC
  export default MDXComponent
}
