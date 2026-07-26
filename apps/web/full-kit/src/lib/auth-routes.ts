import { routeMap } from "@/configs/auth-routes"

const getBasePath = (route: string): string => {
  // Extract the base path (e.g., "/user" from "/user/profile")
  const secondSlash = route.indexOf("/", 1)
  return secondSlash === -1 ? route : route.substring(0, secondSlash)
}

function isRouteType(route: string, type: string) {
  const basePath = getBasePath(route)
  const routeInfo = routeMap.get(basePath)

  // Check if route exists and matches the desired type
  if (routeInfo && routeInfo.type === type) {
    // Return false if route matches any exception, otherwise true.
    if (routeInfo.exceptions) {
      return !routeInfo.exceptions.some((exception) =>
        route.startsWith(exception)
      )
    }
    return true
  }

  // If no matching route, return false
  return false
}

export function isPublicRoute(route: string) {
  return isRouteType(route, "public")
}

export function isGuestRoute(route: string) {
  return isRouteType(route, "guest")
}
