import type { RouteType } from "@/types"

export const routeMap = new Map<string, RouteType>([
  ["/sign-in", { type: "guest" }],
  ["/register", { type: "guest" }],
  ["/forgot-password", { type: "guest" }],
  ["/verify-email", { type: "guest" }],
  ["/new-password", { type: "guest" }],
  ["/", { type: "public" }],
  ["/docs", { type: "public" }],
])
