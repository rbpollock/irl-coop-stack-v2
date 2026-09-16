# Sharing NocoDB interfaces — ship the shape, re-bind the data

**Status: design (current-best).** The non-obvious problem in "how do people share their cool NocoDB
interfaces" is that *share* hides three different acts, and only one of them is safe as a copy. This
doc disambiguates them and pins the one rule that keeps sharing from leaking data.

## The three meanings of "share"

1. **Share the *data*** — give someone access to the rows. That is the RLS/group-seat work
   (`nocodb-integration.md`): a member sees their slice. Solved in principle.
2. **Share the *interface*** (same data, same group) — another member opens the *same* facesheet /
   board / grid, rows scoped to them. This is a **group-seat + role** problem; the "who" picker is the
   share button, and role-as-identity RLS is the enforcement. Small, clean, near-done.
3. **Share the *build* / remix** — "here is my cool interface, use it as a starting point for *your*
   group's version." This is the interesting one, and it is **not opening a shared thing**; it is
   *instantiating a shape into another context under their data + their scope*.

Meanings 2 and 3 differ in kind, not degree. One is *co-viewing*; the other is *forking*. The platform
already has the language for both: the group-"who" picker (`group-who-picker.md`) for co-viewing, and
the **blueprint library** (Robbie's vision) for forking.

## The shape-vs-binding split (the safety rule)

An interface is neither pure data nor pure code — it is a **shape** (schemas, columns, views, layout)
that is **bound** to data (the rows it filters) *at the moment you view it*. So "share" must split the
two, and the rule that keeps it safe is a single sentence:

> **Ship the shape; re-bind the data.** A shared interface never carries one group's rows to another.
> The shape (the template) is portable; the binding (which rows, scoped to whom) is re-instantiated
> per recipient, always through RLS.

Copy the binding → you leak data (a shared interface must not carry over rows). Copy only the shape →
you get a clean template, and re-binding it to the recipient's `app.sub`/role is precisely what RLS
already does. So the hard part of "share" is *not* permissions — it is making the **shape** fully
separable from the **binding** so a template can move without its data.

## Where each meaning lives in the deployed model

| meaning | mechanism | where it is |
|---|---|---|
| share data | role-as-identity RLS | `nocodb-integration.md` (settled principle) |
| share interface (co-view) | group-seat resolved by the "who" picker | `group-who-picker.md` (one shared primitive) |
| share build (remix) | blueprint-library entry + instantiate-to-scope | vision (blueprint library) — not yet built |

## The goal, stated plainly

> **"Share this interface to @other-group" = add the interface's *shape* to the blueprint library, then
> instantiate that shape into @other-group's context, re-bound to their rows through role-as-identity
> RLS.** Data is never shared by copying; only the shape is, and the binding is always re-lived.

Three pieces already on the table compose into it:

1. the **"who" picker** — the share affordance ("@other-group");
2. the **blueprint library** — where shared shapes live;
3. **role-as-identity RLS** — how the copied shape re-binds to "their rows, not mine."

## Non-goals

- No "share the base" that copies rows between groups (the leak this whole split exists to prevent).
- No per-recipient saved connections (the binding is re-lived, not stored).

## Open questions

1. **Is a "shape" a first-class thing in NocoDB?** (schema + views + Interface layout exportable as a
   template?) — this determines whether "blueprint" is a NocoDB-native export or a coop-level
   serialization we define.
2. **Does remix deserve a *new group-operation*** (e.g. `adopt` / `instantiate`), or is it just
   "the blueprint library + the who-picker"? — lean: it is the latter, no new op, until a real group
   needs distinct custody semantics for a template.
