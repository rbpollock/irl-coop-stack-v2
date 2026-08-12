import { NextResponse } from "next/server"

import type { NextRequest } from "next/server"

// Plane projects for the dashboard nav submenu — per-member, the fleet way:
// the member's coop_session cookie is exchanged through the real OIDC chain
// (plane initiate → gateway instant code → plane callback → plane session),
// then the projects API is read with that session. No shared secrets: the
// callback handles the client-secret exchange server-side inside plane.
const PLANE_BASE = process.env.PLANE_URL ?? "https://plane.irl.coop"
const WORKSPACE = process.env.PLANE_WORKSPACE ?? "coop-test"
const CALLBACK = `${PLANE_BASE}/auth/oidc/callback/`
const TTL_MS = 10 * 60 * 1000

type PlaneProject = { id: string; name: string; identifier: string }

// per-member plane session cookie cache (keyed by coop_session value)
const sessionCache = new Map<string, { cookie: string; expires: number }>()

function lastSetCookie(res: Response): string {
  const all = (
    res.headers as unknown as { getSetCookie?: () => string[] }
  ).getSetCookie?.()
  if (all && all.length) return all[all.length - 1]
  return res.headers.get("set-cookie") ?? ""
}

export const dynamic = "force-dynamic"

async function fetchProjects(planeCookie: string) {
  const res = await fetch(
    `${PLANE_BASE}/api/workspaces/${WORKSPACE}/projects/`,
    {
      headers: { Cookie: planeCookie },
      cache: "no-store",
    }
  )
  if (!res.ok) return null
  const list = (await res.json()) as PlaneProject[]
  return list.map((p) => ({
    id: p.id,
    name: p.name,
    // plane's route is :workspaceSlug/projects/:projectId/issues (plural)
    url: `/${WORKSPACE}/projects/${p.id}/issues`,
  }))
}

export async function GET(request: NextRequest) {
  const coop = request.cookies.get("coop_session")?.value
  if (!coop) return NextResponse.json({ error: "no session" }, { status: 401 })

  const cached = sessionCache.get(coop)
  if (cached && cached.expires > Date.now()) {
    const projects = await fetchProjects(cached.cookie)
    return projects
      ? NextResponse.json({ projects })
      : NextResponse.json({ error: "plane projects failed" }, { status: 502 })
  }

  try {
    // 1. plane initiate — opens the plane session (state) + bounces to the gateway
    const init = await fetch(`${PLANE_BASE}/auth/oidc/`, {
      headers: { Cookie: `coop_session=${coop}` },
      redirect: "manual",
    })
    const initLoc = init.headers.get("location") ?? ""
    const planeSession = lastSetCookie(init)
    if (!initLoc || !planeSession)
      return NextResponse.json({ error: "initiate failed" }, { status: 502 })

    // 2. gateway authorize — the member's coop_session returns an instant code
    const authz = await fetch(initLoc, {
      headers: { Cookie: `coop_session=${coop}` },
      redirect: "manual",
    })
    const codeUrl = authz.headers.get("location") ?? ""
    if (!codeUrl.startsWith(CALLBACK)) {
      return NextResponse.json({ error: "authorize failed" }, { status: 502 })
    }

    // 3. plane callback — exchanges the code, logs the member in (session cookie)
    const cb = await fetch(codeUrl, {
      headers: { Cookie: `coop_session=${coop}; ${planeSession}` },
      redirect: "manual",
    })
    const loginCookie = lastSetCookie(cb) || planeSession

    sessionCache.set(coop, {
      cookie: loginCookie,
      expires: Date.now() + TTL_MS,
    })
    const projects = await fetchProjects(loginCookie)
    return projects
      ? NextResponse.json({ projects })
      : NextResponse.json({ error: "plane projects failed" }, { status: 502 })
  } catch {
    return NextResponse.json(
      { error: "plane exchange failed" },
      { status: 502 }
    )
  }
}
