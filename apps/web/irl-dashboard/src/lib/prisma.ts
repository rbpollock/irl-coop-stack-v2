import { PrismaClient } from "@prisma/client"

const prismaClientSingleton = () => new PrismaClient()

declare global {
  // Prevent TypeScript from complaining about the global prisma variable
  // eslint-disable-next-line no-var
  var prisma: undefined | ReturnType<typeof prismaClientSingleton>
}

const db = globalThis.prisma ?? prismaClientSingleton()

// If not in production, reuse the Prisma instance across hot reloads
if (process.env.NODE_ENV !== "production") globalThis.prisma = db

export { db }
