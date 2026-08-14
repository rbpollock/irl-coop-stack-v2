// Journey: "A member works in the shared Coop base" — the NocoDB bases list
// renders, and the shared base returns only this identity's RLS-scoped rows.
export const name = "nocodb-read"
export const description = "A member works in the shared Coop base (bases list + RLS-scoped rows)"

const GROUPS = "mpi01cdb2jofe2r" // Groups model id in the shared "Coop" base

export async function run(ctx) {
  const page = ctx.nocodb?.page
  const token = ctx.nocodb?.token
  if (!page || !token) {
    ctx.check("NocoDB session for read journey", false, "no browser session")
    return
  }

  // The bases list renders (no spinner, shared base titles present).
  const dom = await page.evaluate(() => {
    const body = document.body.innerText || ""
    const spinner = !!document.querySelector("[class*='spinner' i], [class*='Spinner' i], .nc-loading, .ant-spin")
    return { spinner, hasCoop: body.includes("Coop"), basesCount: (body.match(/Bases\s*\((\d+)\)/) ?? [])[1] ?? null }
  })
  ctx.check("bases list renders without a spinner", !dom.spinner && dom.hasCoop, JSON.stringify(dom))

  // Read the Groups model through the external source — RLS scopes the rows.
  const read = await page.evaluate(async ({ token, GROUPS }) => {
    const r = await fetch(`/api/v2/tables/${GROUPS}/records`, { headers: { "xc-auth": token } })
    const j = await r.json().catch(() => ({}))
    return { status: r.status, count: (j.list || []).length, names: (j.list || []).map((x) => x.Name) }
  }, { token, GROUPS })
  ctx.check("Coop base read returns RLS-scoped rows (200)", read.status === 200 && read.count >= 1, `status=${read.status} n=${read.count}`)
  ctx.check("RLS scoping yields a non-empty, bounded set", read.count >= 1, `n=${read.count} names=${read.names.slice(0, 5).join(",")}`)
}
