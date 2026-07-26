import { NextResponse } from "next/server"

import { userData } from "@/data/user"

import { SignInSchema } from "@/schemas/sign-in-schema"

export async function POST(req: Request) {
  const body = await req.json()
  const parsedData = SignInSchema.safeParse(body)

  // If validation fails, return an error response with a 400 status
  if (!parsedData.success) {
    return NextResponse.json(parsedData.error, { status: 400 })
  }

  const { email, password } = parsedData.data

  try {
    // If provided email and password match the stored user data
    if (userData.email !== email || userData.password !== password) {
      return NextResponse.json(
        { message: "Invalid email or password", email },
        { status: 401 }
      )
    }

    // Return success response with user data if credentials are correct
    return NextResponse.json(
      {
        id: userData.id,
        name: userData.name,
        email: userData.email,
        avatar: userData.avatar,
        status: userData.status,
      },
      { status: 200 }
    )
  } catch (e) {
    console.error("Error signing in:", e)
    return NextResponse.json({ error: "Error signing in" }, { status: 500 })
  }
}
