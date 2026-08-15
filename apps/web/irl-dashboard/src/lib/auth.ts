import { getServerSession } from "next-auth"

import { authOptions } from "@/configs/next-auth"

export async function getSession() {
  return await getServerSession(authOptions)
}

export async function authenticateUser() {
  const session = await getSession()

  if (!session || !session.user?.id) {
    throw new Error("Unauthorized user.")
  }

  return session.user
}
