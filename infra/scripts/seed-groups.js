// Declarative seed groups: creates any group whose slug is free (POST /api/v1/groups)
// and indexes open groups' profiles into the RAG "groups" area so the docs search
// can find them. Idempotent — re-running is a no-op for already-seeded groups.
//
// Run via infra/scripts/seed-groups.sh (which also marks the RAG area public).
const fs = require("fs")
const yaml = require("js-yaml")
const jwt = require("../../node_modules/jsonwebtoken")

const ROOT = "/home/service/development/irl-coop-stack-v2"
const COOP_API = "http://localhost:3001"
const RAG_API = "http://127.0.0.1:8000"
const GROUPS_AREA = "groups"

// Seed identity: a dedicated service principal. Its sub holds the owner seat of
// every seed group so they survive independent of any one member.
const env = fs.readFileSync(`${ROOT}/apps/coop-api/.env`, "utf8")
const b64 = env.match(/COOP_JWT_PRIVATE_KEY_B64=(.+)/)[1].trim()
const privateKey = Buffer.from(b64, "base64").toString("utf8")
const token = jwt.sign({ sub: "seed-bot", groups: [] }, privateKey, {
  algorithm: "RS256",
  keyid: "2yMKHsAb8UD1QHtTd2LAC2-GCu2k1p-WC5gTI9LLvT8",
  issuer: "https://api.irl.coop",
  audience: "irl-coop",
  expiresIn: "10m",
})
const AUTH = { Authorization: `Bearer ${token}` }

async function json(method, path, body) {
  const res = await fetch(`${COOP_API}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...AUTH },
    body: body ? JSON.stringify(body) : undefined,
  })
  const text = await res.text()
  try { return { status: res.status, data: JSON.parse(text) } } catch { return { status: res.status, data: text } }
}

async function ragJson(method, path, body) {
  const res = await fetch(`${RAG_API}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...AUTH },
    body: body ? JSON.stringify(body) : undefined,
  })
  return { status: res.status, data: await res.json() }
}

async function ensureGroupsArea() {
  const list = await ragJson("GET", "/areas")
  const existing = (list.data?.items ?? []).find((a) => a.name === GROUPS_AREA)
  if (existing) return existing.id
  const created = await ragJson("POST", "/areas", { name: GROUPS_AREA, description: "Public group profiles — searchable by name and purpose." })
  if (created.status === 201) return created.data.id
  throw new Error(`could not create groups area: ${JSON.stringify(created.data)}`)
}

async function indexProfile(areaId, group) {
  const markdown = `# ${group.name}\n\n${group.description}\n\nVisibility: ${group.privacy} · recipe: ${group.recipe}`
  const form = new FormData()
  form.append("file", new Blob([markdown], { type: "text/markdown" }), `group-${group.slug}.md`)
  const res = await fetch(`${RAG_API}/areas/${areaId}/documents`, { method: "POST", headers: AUTH, body: form })
  const data = await res.json()
  return { status: res.status, document_id: data?.document?.id ?? null }
}

;(async () => {
  const spec = yaml.load(fs.readFileSync(`${ROOT}/infra/instances/dev/etc/seed-groups.yaml`, "utf8"))
  const groupsAreaId = await ensureGroupsArea()
  console.log(`groups area: ${groupsAreaId}`)

  for (const g of spec.groups) {
    const created = await json("POST", "/api/v1/groups", { name: g.name, slug: g.slug, privacy: g.privacy })
    if (created.status === 409) {
      console.log(`  ${g.slug}: already seeded (skip)`)
      continue
    }
    if (created.status !== 201) {
      console.log(`  ${g.slug}: FAILED ${created.status} ${JSON.stringify(created.data)}`)
      continue
    }
    const groupId = created.data.id
    let profile = null
    if (g.privacy === "open") {
      profile = await indexProfile(groupsAreaId, g)
    }
    console.log(`  ${g.slug}: created (${groupId.slice(0, 8)}) privacy=${g.privacy} indexed=${profile?.document_id ? profile.document_id.slice(0, 8) : "n/a"}`)
  }
})()
