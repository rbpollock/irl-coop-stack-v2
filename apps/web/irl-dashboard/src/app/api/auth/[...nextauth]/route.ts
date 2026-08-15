import NextAuth from "next-auth"

import { authOptions } from "@/configs/next-auth"

// Create a NextAuth handler using the imported options
const handler = NextAuth(authOptions)

// Export the handler to be used as GET and POST methods for Route Handlers
// More info: https://next-auth.js.org/configuration/initialization#route-handlers-app
export { handler as GET, handler as POST }
