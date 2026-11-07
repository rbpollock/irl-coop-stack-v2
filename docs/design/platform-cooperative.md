# The Infrastructure as a Platform Cooperative

Status: design · 2026-10-04.

irl.coop is not a SaaS company. It is a **cooperative that runs infrastructure** — for its own
members, for member groups, and for allied organizations. The platform itself is member-owned,
democratically controlled, and surplus is returned to members.

The infrastructure stays under member control. No venture capital, no acquisition, no data mining.
The code is open-source; the deployment is the coop's.

---

## What already works (live)

| Primitive | How it works | Where to read more |
|---|---|---|
| **Self-hosted stack** | 38 apps, one Traefik edge, shared Citus Postgres, self-managed TLS. | [`SYSTEM-MAP.md`](/design/SYSTEM-MAP) · [`RISKS.md`](/design/RISKS) · [`infra-management-monitoring.md`](/design/infra-management-monitoring) |
| **Cost model** | Member dues + group infrastructure contributions cover hosting + stewardship. | [`cost-model.md`](/design/cost-model) |
| **No platform lock-in** | Delete the `resource_scopes` row = the app becomes independent. | [`declared-binding-registry.md`](/design/declared-binding-registry) |
| **Open-source licensing** | MIT (dashboard), GPL-3 (circuits), coop code is what the group decides. | [`landing-page-claims-audit.md`](/design/landing-page-claims-audit) |
| **Group-operated nodes** | A group can run its own Android + SIM at a physical node, forwarding through Telnyx. | [`group-operated-stack.md`](/design/group-operated-stack) · [`telephony.md`](/design/telephony) |

---

## What is designed, not yet built

| Feature | Status | Where to read more |
|---|---|---|
| **Platform governance** | The irl.coop group (as a Safe) votes on: infrastructure spending, app admission, steward compensation, federation partnerships. | [`coop-launch-and-roadmap-handoff.md`](/design/coop-launch-and-roadmap-handoff) |
| **Steward rotation** | Technical steward is elected, term-limited, and accountable. Safe threshold enforces this. | [`transfer-authority.md`](/design/transfer-authority) |
| **Coop launch handoff** | The founding process: legal entity, initial members, treasury seed, first vote. | [`coop-launch-and-roadmap-handoff.md`](/design/coop-launch-and-roadmap-handoff) |
| **Fiscal sponsorship** | Structure for groups that are not yet legal entities to receive funds through the platform. | [`fiscal-sponsorship-pitch-video.md`](/design/fiscal-sponsorship-pitch-video) |

---

## Open questions

- **Legal entity**: In which jurisdiction is the platform cooperative incorporated? This decides
  tax, liability, and regulatory exposure. The `PAYMENTS_ENTITY` field exists because this is undecided.
- **Steward compensation**: How is technical labor priced and approved? Hourly, retainer, or
  outcome-based? Who audits the steward's work?

---

## Honest limits

- The coop itself is not yet a group on the platform. irl.coop is a design, a Safe narrative,
  not a deployed group with members voting.
- No surplus exists to return. The cost model is aspirational until real dues flow.

See [`irl-coop-overview.md`](/design/irl-coop-overview) for how this pillar fits into the whole platform.
