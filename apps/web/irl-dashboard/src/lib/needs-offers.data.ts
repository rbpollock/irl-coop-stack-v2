// needs-offers.data.ts — the stress-test corpus.
//
// Generated from the landing-page recipes × regions, so the dataset scales to
// hundreds of postings and the "zones" lens has something to filter. Each
// posting carries the five dimensions from the matching spec: shape, type,
// temporality, urgency, location.

export type Shape = "physical" | "remote" | "financial"

export type NeedType =
  | "logistical"
  | "staffing"
  | "tool"
  | "advocacy"
  | "manual labor"
  | "planning"
  | "engineering"
  | "research"
  | "driving"
  | "goods"
  | "space"
  | "funding"
  | "expertise"
  | "care"
  | "equipment"

export type Temporality = "now" | "this week" | "this season" | "recurring" | "one-off"
export type Urgency = "high" | "medium" | "low"

export type Posting = {
  id: string
  have: boolean
  what: string
  group: string
  shape: Shape
  type: NeedType
  temporality: Temporality
  urgency: Urgency
  location: string
  km?: number
}

export type MatchLink = {
  source: string
  target: string
  weight: number
}

// Deterministic pseudo-random so the layout is stable across renders.
function hash(str: string): number {
  let h = 0
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) % 100000
  return h / 100000
}

type RecipePosting = Omit<Posting, "id" | "group" | "location" | "km">

type Recipe = { name: string; postings: RecipePosting[] }

const RECIPES: Recipe[] = [
  {
    name: "Neighborhood growing team",
    postings: [
      { what: "compost delivery", have: true, shape: "physical", type: "logistical", temporality: "this season", urgency: "medium" },
      { what: "surplus seedlings", have: true, shape: "physical", type: "goods", temporality: "this season", urgency: "low" },
      { what: "rototilling", have: false, shape: "physical", type: "manual labor", temporality: "now", urgency: "high" },
      { what: "watering coverage", have: false, shape: "physical", type: "staffing", temporality: "recurring", urgency: "medium" },
      { what: "shared greenhouse space", have: true, shape: "physical", type: "space", temporality: "this season", urgency: "low" },
      { what: "soil test", have: false, shape: "remote", type: "research", temporality: "now", urgency: "low" },
      { what: "tool sharpening", have: false, shape: "physical", type: "tool", temporality: "now", urgency: "medium" },
      { what: "harvest help", have: false, shape: "physical", type: "manual labor", temporality: "this season", urgency: "high" },
    ],
  },
  {
    name: "Local theater",
    postings: [
      { what: "stage carpentry", have: false, shape: "physical", type: "engineering", temporality: "this week", urgency: "high" },
      { what: "costume sewing", have: false, shape: "physical", type: "manual labor", temporality: "this week", urgency: "medium" },
      { what: "ushers", have: false, shape: "physical", type: "staffing", temporality: "one-off", urgency: "medium" },
      { what: "rehearsal space", have: true, shape: "physical", type: "space", temporality: "recurring", urgency: "low" },
      { what: "lighting rig", have: false, shape: "physical", type: "equipment", temporality: "this week", urgency: "high" },
      { what: "poster graphics", have: false, shape: "remote", type: "planning", temporality: "this week", urgency: "medium" },
      { what: "prop storage", have: true, shape: "physical", type: "space", temporality: "recurring", urgency: "low" },
      { what: "set-pickup driving", have: false, shape: "physical", type: "driving", temporality: "this week", urgency: "high" },
      { what: "grant writing", have: false, shape: "remote", type: "advocacy", temporality: "this season", urgency: "medium" },
    ],
  },
  {
    name: "Tool library",
    postings: [
      { what: "lawnmower", have: true, shape: "physical", type: "tool", temporality: "recurring", urgency: "low" },
      { what: "nail gun", have: true, shape: "physical", type: "tool", temporality: "recurring", urgency: "low" },
      { what: "tool repair", have: false, shape: "physical", type: "engineering", temporality: "recurring", urgency: "medium" },
      { what: "check-in volunteers", have: false, shape: "physical", type: "staffing", temporality: "recurring", urgency: "medium" },
      { what: "shelving build", have: false, shape: "physical", type: "engineering", temporality: "now", urgency: "medium" },
      { what: "workshop space", have: true, shape: "physical", type: "space", temporality: "recurring", urgency: "low" },
      { what: "inventory app", have: false, shape: "remote", type: "engineering", temporality: "now", urgency: "medium" },
      { what: "drill press", have: false, shape: "physical", type: "tool", temporality: "recurring", urgency: "low" },
      { what: "tool-pickup driving", have: false, shape: "physical", type: "driving", temporality: "recurring", urgency: "medium" },
    ],
  },
  {
    name: "Childcare co-op",
    postings: [
      { what: "backup caregiver", have: false, shape: "physical", type: "care", temporality: "recurring", urgency: "high" },
      { what: "play space", have: false, shape: "physical", type: "space", temporality: "recurring", urgency: "low" },
      { what: "after-school hours", have: true, shape: "physical", type: "care", temporality: "recurring", urgency: "low" },
      { what: "first-aid training", have: false, shape: "physical", type: "planning", temporality: "this season", urgency: "medium" },
      { what: "meal prep", have: false, shape: "physical", type: "logistical", temporality: "recurring", urgency: "medium" },
      { what: "babysitting swap", have: true, shape: "physical", type: "care", temporality: "recurring", urgency: "low" },
      { what: "scheduling app", have: false, shape: "remote", type: "engineering", temporality: "now", urgency: "medium" },
      { what: "playground supervision", have: false, shape: "physical", type: "staffing", temporality: "recurring", urgency: "medium" },
    ],
  },
  {
    name: "Craft circle",
    postings: [
      { what: "knitting lessons", have: true, shape: "remote", type: "expertise", temporality: "recurring", urgency: "low" },
      { what: "yarn donations", have: false, shape: "physical", type: "goods", temporality: "recurring", urgency: "low" },
      { what: "dyeing studio", have: true, shape: "physical", type: "space", temporality: "recurring", urgency: "low" },
      { what: "material-pooling fund", have: false, shape: "financial", type: "funding", temporality: "this season", urgency: "medium" },
      { what: "pattern digitization", have: false, shape: "remote", type: "research", temporality: "now", urgency: "low" },
      { what: "floor loom", have: true, shape: "physical", type: "tool", temporality: "recurring", urgency: "low" },
      { what: "workshop rental", have: false, shape: "physical", type: "space", temporality: "this week", urgency: "medium" },
    ],
  },
  {
    name: "Food skills",
    postings: [
      { what: "knife-skills class", have: true, shape: "physical", type: "expertise", temporality: "recurring", urgency: "low" },
      { what: "commercial kitchen", have: false, shape: "physical", type: "space", temporality: "recurring", urgency: "medium" },
      { what: "tallow equipment", have: false, shape: "physical", type: "equipment", temporality: "now", urgency: "low" },
      { what: "food-safety certification", have: true, shape: "remote", type: "planning", temporality: "this season", urgency: "low" },
      { what: "teaching volunteers", have: false, shape: "physical", type: "staffing", temporality: "recurring", urgency: "medium" },
      { what: "food dehydrator", have: false, shape: "physical", type: "equipment", temporality: "now", urgency: "low" },
    ],
  },
  {
    name: "Farmer exchange",
    postings: [
      { what: "manure", have: true, shape: "physical", type: "goods", temporality: "this season", urgency: "medium" },
      { what: "hay", have: false, shape: "physical", type: "goods", temporality: "this season", urgency: "high" },
      { what: "harvest hands", have: false, shape: "physical", type: "manual labor", temporality: "this season", urgency: "high" },
      { what: "tractor time", have: true, shape: "physical", type: "tool", temporality: "this season", urgency: "medium" },
      { what: "fencing repair", have: false, shape: "physical", type: "manual labor", temporality: "now", urgency: "medium" },
      { what: "saved seed", have: true, shape: "physical", type: "goods", temporality: "this season", urgency: "low" },
      { what: "livestock transport", have: false, shape: "physical", type: "driving", temporality: "recurring", urgency: "high" },
      { what: "irrigation planning", have: false, shape: "remote", type: "engineering", temporality: "this season", urgency: "medium" },
    ],
  },
  {
    name: "Hand-me-downs",
    postings: [
      { what: "outgrown kids' clothes", have: true, shape: "physical", type: "goods", temporality: "recurring", urgency: "low" },
      { what: "sorting help", have: false, shape: "physical", type: "manual labor", temporality: "recurring", urgency: "medium" },
      { what: "drop-off point", have: false, shape: "physical", type: "space", temporality: "recurring", urgency: "low" },
      { what: "mending", have: false, shape: "physical", type: "manual labor", temporality: "recurring", urgency: "low" },
      { what: "storage bins", have: true, shape: "physical", type: "equipment", temporality: "recurring", urgency: "low" },
      { what: "donation driving", have: false, shape: "physical", type: "driving", temporality: "recurring", urgency: "medium" },
    ],
  },
  {
    name: "Solutions library",
    postings: [
      { what: "story collection", have: false, shape: "remote", type: "research", temporality: "recurring", urgency: "medium" },
      { what: "anonymization review", have: false, shape: "remote", type: "advocacy", temporality: "recurring", urgency: "medium" },
      { what: "story-extraction facilitation", have: true, shape: "remote", type: "expertise", temporality: "recurring", urgency: "low" },
      { what: "publishing site", have: false, shape: "remote", type: "engineering", temporality: "now", urgency: "medium" },
      { what: "translation", have: false, shape: "remote", type: "research", temporality: "recurring", urgency: "low" },
    ],
  },
  {
    name: "Gatherings",
    postings: [
      { what: "venue", have: false, shape: "physical", type: "space", temporality: "one-off", urgency: "high" },
      { what: "setup crew", have: false, shape: "physical", type: "manual labor", temporality: "one-off", urgency: "high" },
      { what: "PA system", have: true, shape: "physical", type: "equipment", temporality: "one-off", urgency: "low" },
      { what: "catering", have: false, shape: "physical", type: "logistical", temporality: "one-off", urgency: "high" },
      { what: "facilitator", have: false, shape: "remote", type: "expertise", temporality: "one-off", urgency: "medium" },
      { what: "promotion", have: false, shape: "remote", type: "planning", temporality: "this week", urgency: "medium" },
    ],
  },
  {
    name: "Civic engagement",
    postings: [
      { what: "poll workers", have: false, shape: "physical", type: "staffing", temporality: "one-off", urgency: "high" },
      { what: "rides to polls", have: false, shape: "physical", type: "driving", temporality: "one-off", urgency: "high" },
      { what: "registration tabling", have: false, shape: "physical", type: "advocacy", temporality: "this week", urgency: "medium" },
      { what: "know-your-rights training", have: true, shape: "remote", type: "expertise", temporality: "recurring", urgency: "low" },
      { what: "canvassing maps", have: false, shape: "remote", type: "research", temporality: "this season", urgency: "medium" },
      { what: "phone banking", have: false, shape: "remote", type: "staffing", temporality: "this season", urgency: "medium" },
    ],
  },
]

export const REGIONS = [
  "Vermont",
  "Western Mass",
  "Hudson Valley",
  "Coastal Maine",
  "Boston Metro",
  "Pioneer Valley",
]

function slug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")
}

// Build the full corpus: every recipe instantiated in every region. Physical
// postings get a deterministic distance (km) from the region's center so the
// "near me" lens can filter by radius.
export function buildPostings(): Posting[] {
  const out: Posting[] = []
  for (const region of REGIONS) {
    for (const recipe of RECIPES) {
      for (const p of recipe.postings) {
        const id = `${slug(region)}-${slug(recipe.name)}-${slug(p.what)}`
        out.push({
          ...p,
          id,
          group: `${recipe.name} · ${region}`,
          location: region,
          km: p.shape === "physical" ? 2 + Math.round(hash(id) * 58) : undefined,
        })
      }
    }
  }
  return out
}

// Potential matches: for each need, the top-3 offers of the same type in the
// same region, weighted by a deterministic "fit" score. (In the real system
// this weight is the RAG semantic similarity — here it's a stable stand-in so
// the "distance of likely weights" gradient shows.)
export function buildLinks(postings: Posting[]): MatchLink[] {
  const byRegion = new Map<string, Posting[]>()
  for (const p of postings) {
    if (!byRegion.has(p.location)) byRegion.set(p.location, [])
    byRegion.get(p.location)!.push(p)
  }

  const links: MatchLink[] = []
  for (const ps of byRegion.values()) {
    const offers = ps.filter((p) => p.have && p.shape !== "financial")
    const needs = ps.filter((p) => !p.have && p.shape !== "financial")
    for (const need of needs) {
      const candidates = offers
        .filter((o) => o.type === need.type)
        .map((o) => ({ o, weight: 0.4 + hash(`${o.id}↔${need.id}`) * 0.55 }))
        .sort((a, b) => b.weight - a.weight)
        .slice(0, 3)
      for (const { o, weight } of candidates) {
        links.push({ source: o.id, target: need.id, weight: Math.round(weight * 100) / 100 })
      }
    }
  }
  return links
}
