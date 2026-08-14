// Journey: "A member edits a group row" — the write path carries the identity
// (app.sub injected on knex queries), so an owner's PATCH round-trips and the
// row is restored afterwards.
export const name = "nocodb-write"
export const description = "A member edits a group row through NocoDB (write-path identity injection)"

const GROUPS = "mpi01cdb2jofe2r"

export async function run(ctx) {
  const page = ctx.nocodb?.page
  const token = ctx.nocodb?.token
  if (!page || !token) {
    ctx.check("NocoDB session for write journey", false, "no browser session")
    return
  }

  const result = await page.evaluate(async ({ token, GROUPS }) => {
    const api = async (method, path, body) => {
      const res = await fetch(path, {
        method,
        headers: { "Content-Type": "application/json", "xc-auth": token },
        body: body ? JSON.stringify(body) : undefined,
      })
      let json = {}
      try { json = await res.json() } catch { /* noop */ }
      return { status: res.status, json }
    }
    const read = async () => (await api("GET", `/api/v2/tables/${GROUPS}/records`)).json.list || []
    const rows = await read()
    if (!rows.length) return { error: "no rows in scope", n: 0 }

    // PATCH the first visible row; it is owner-owned in the current data shape.
    // A member-only (non-owned) row would be filtered by the RLS UPDATE policy,
    // so a silent no-change here is itself a signal we assert against.
    const row = rows[0]
    const before = row.Description ?? null
    const target = "write-" + Date.now()
    const up = await api("PATCH", `/api/v2/tables/${GROUPS}/records`, [{ Id: row.Id, Description: target }])
    const after = (await read()).find((r) => r.Id === row.Id)
    const changed = after?.Description === target
    await api("PATCH", `/api/v2/tables/${GROUPS}/records`, [{ Id: row.Id, Description: before ?? "" }])
    return { status: up.status, changed, name: row.Name, n: rows.length }
  }, { token, GROUPS })

  if (result.error) {
    ctx.check("write path: a row is in scope", false, result.error)
    return
  }
  ctx.check(
    "owner PATCH round-trips (write path identity)",
    result.status === 200 && result.changed === true,
    `status=${result.status} changed=${result.changed} row=${result.name}`,
  )
}
