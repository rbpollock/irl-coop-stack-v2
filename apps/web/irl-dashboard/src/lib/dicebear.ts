import { Avatar, Style } from "@dicebear/core"

import glyphs from "@dicebear/styles/glyphs.json"

// Self-hosted DiceBear "glyphs" style (no api.dicebear.com call — the seed
// never leaves the box). The Style is reusable across avatars per the DiceBear
// v10 docs, so build it once and render many.
const glyphStyle = new Style(glyphs)

// Deterministic SVG avatars are cheap to generate but a profile page can render
// dozens; cache by seed so each identity renders exactly once.
const cache = new Map<string, string>()

/** Deterministic self-hosted DiceBear glyphs avatar (SVG data URI) from a seed. */
export function dicebearAvatar(seed: string): string {
  let uri = cache.get(seed)
  if (!uri) {
    uri = new Avatar(glyphStyle, { seed }).toDataUri()
    cache.set(seed, uri)
  }
  return uri
}
