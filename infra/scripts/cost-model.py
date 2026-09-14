#!/usr/bin/env python3
"""irl.coop cost model emitter — stdlib only.

Single source for the cost numbers used by the intro-video series
(docs/design/intro-video-series.md §4) and by any pricing surface:

  V3  side-by-side  : enterprise (per-seat) | mid-tier (fixed fee) | irl.coop
  V8  self-sustaining: node cost vs node inflow, and the crossover

Rules the code ENFORCES (not just documents):

  * a price with status != "verified" never enters a total — it is listed as an
    open item instead. No silent zeroes, no guessed numbers.
  * node / revenue figures marked illustrative are watermarked in the output, so
    an unfilled placeholder cannot quietly become a claim on screen.
  * stewardship (a person's time) is a SEPARATE line from infrastructure — never
    folded in, because that is what makes later "self-sustaining" claims collapse.

Usage:
  cost-model.py                     print the markdown report
  cost-model.py --json              print the machine-readable model
  cost-model.py --inject DOC        replace the generated block in DOC in place
  cost-model.py --data FILE         use an alternate data file
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "docs", "design", "cost-model.data.json")
INSTANCE = os.path.join(ROOT, "infra", "instances", "dev", "instance.yaml")

BEGIN = "<!-- BEGIN GENERATED: cost-model.py -->"
END = "<!-- END GENERATED: cost-model.py -->"

TIERS = ("lean", "standard", "enterprise")
NODE_KEYS = ("hosting_monthly", "hardware_amortized_monthly", "dns_domain_monthly",
             "backup_storage_monthly")


# ---------------------------------------------------------------- data loading
def load(data_path=DATA):
    with open(data_path) as fh:
        return json.load(fh)


def declared_apps(instance_path=INSTANCE):
    """Names under `apps:` in the instance tree — for the coverage cross-check."""
    apps, in_apps = [], False
    try:
        with open(instance_path) as fh:
            for line in fh:
                if line.startswith("apps:"):
                    in_apps = True
                    continue
                if in_apps:
                    s = line.strip()
                    if s.startswith("- "):
                        apps.append(s[2:].strip())
                    elif s and not line.startswith((" ", "\t")):
                        break
    except OSError:
        pass
    return apps


# ------------------------------------------------------------------- modelling
def node_monthly(data):
    n = data["node"]
    return sum(float(n.get(k) or 0) for k in NODE_KEYS)


def stewardship_monthly(data):
    s = data["stewardship"]
    return float(s.get("hours_per_month") or 0) * float(s.get("hourly_rate") or 0)


def node_external_monthly(data):
    """Third-party costs the node pays and CANNOT make free — carrier numbers, etc.

    Kept separate from infrastructure: 'open source makes it free' is true of
    licences and false of a phone number, and the distinction is the difference
    between a credible claim and one a skeptic disposes of in one line.
    """
    ext = data.get("node_external") or {}
    return sum(float(i.get("per_unit_month") or 0) * float(i.get("count") or 0)
               for i in (ext.get("items") or []))


def usage_layer(comps, volume, unit, free_of_stored=None):
    """Usage-metered comparables priced at a scenario volume.

    `unit` is 'per_1k_loads' (divisor 1000) or 'per_gb' (divisor 1). Free
    allowances are honoured per vendor, because pretending they don't exist would
    produce a dramatic number any reader can disprove by opening the vendor's
    pricing page. A row whose allowance covers the volume, or whose rate is
    deliberately unquoted, is reported rather than silently counted as $0.
    """
    divisor = 1000.0 if unit == "per_1k_loads" else 1.0
    rows = []
    for c in comps:
        if c["unit"] != unit or c["status"] != "verified" or c.get("price") is None:
            continue
        free = float(c.get("free_monthly") or 0)
        if free_of_stored and c.get("free_multiple_of_stored"):
            free = float(c["free_multiple_of_stored"]) * free_of_stored
        billable = max(volume - free, 0.0)
        rate = float(c["price"])
        unpriced = billable > 0 and rate == 0 and not c.get("zero_is_the_rate")
        rows.append({
            "slice": c["slice"], "vendor": c["vendor"], "product": c["product"],
            "rate": rate, "free": free, "volume": volume,
            "billable": round(billable, 2),
            "monthly": round(0.0 if unpriced else billable / divisor * rate, 2),
            "unpriced": unpriced,
            "source": c.get("source"), "note": c.get("note"),
        })
    return sorted(rows, key=lambda r: r["monthly"])


def per_1k_layer(comps, scenario, unit, volume_key):
    return usage_layer(comps, float(scenario.get(volume_key) or 0), unit)


def storage_summary(data, comps, scenario):
    """The storage slice: measured bytes, the node's own $/GB, and the vendors.

    The node's storage is deliberately NOT added to any total — its disk is
    already inside the infrastructure line, so a separate storage charge would be
    a double count. What is useful is the RATE comparison and the shape
    difference (one pool vs a quota per member).
    """
    st = data.get("storage") or {}
    per_tb = float(st.get("hardware_cost_per_tb") or 0)
    months = float(st.get("amortization_months") or 36) or 36
    node_rate = per_tb / 1024.0 / months
    live = float(st.get("live_data_gb") or 0)
    egress_vol = float(scenario.get("egress_gb_monthly") or 0)
    return {
        "measured_total_gb": st.get("measured_total_gb"),
        "live_data_gb": live,
        "build_scratch_gb": st.get("build_scratch_gb"),
        "measured_on": st.get("measured_on"),
        "method": st.get("method"),
        "breakdown": st.get("breakdown", []),
        "unmeasured": st.get("unmeasured", []),
        "findings": st.get("findings", []),
        "disk": st.get("disk", {}),
        "illustrative": bool(st.get("illustrative")),
        "node_rate_per_gb_month": round(node_rate, 5),
        "node_storage_monthly": round(live * node_rate, 3),
        "storage": usage_layer(comps, live, "per_gb_month"),
        "egress": usage_layer(comps, egress_vol, "per_gb", free_of_stored=live),
        "egress_volume": egress_vol,
        "fixed_tiers": st.get("fixed_tiers", []),
    }


def scale_model(data, comps):
    """What a movement of 10k-50k participants costs, both ways.

    The commercial side is a LOWER BOUND by construction: only slices with a
    verified rate at this volume are priced, and the cheapest verified rate in
    each slice is used. Everything the vendors have taken off the self-serve menu
    is listed as unpriced rather than guessed — which is the whole finding, not a
    gap in the model.
    """
    sc = data.get("scale") or {}
    a = sc.get("assumptions", {})
    rates = sc.get("scale_rates", [])
    hourly = float((data.get("stewardship") or {}).get("hourly_rate") or 0)

    by_slice = {}
    for r in rates:
        by_slice.setdefault(r["slice"], []).append(r)

    out = []
    for s in sc.get("scenarios", []):
        rows, unpriced, commercial = [], [], 0.0
        for slice_name, seats in (s.get("seats") or {}).items():
            options = sorted(by_slice.get(slice_name, []), key=lambda r: r["rate"])
            if not options:
                unpriced.append({"slice": slice_name, "seats": seats})
                continue
            r = options[0]
            monthly = round(seats * float(r["rate"]), 2)
            commercial += monthly
            rows.append({"slice": slice_name, "vendor": r["vendor"], "product": r["product"],
                         "rate": r["rate"], "seats": seats, "monthly": monthly,
                         "source": r.get("source"), "note": r.get("note")})
        hosts = int(s.get("hosts") or 1)
        host_cost = round(hosts * float(a.get("node_host_monthly") or 0), 2)
        egress_tb = float(s.get("egress_tb_monthly") or 0)
        bw = round(egress_tb * float(a.get("bandwidth_cost_per_tb") or 0), 2)
        hours = float(s.get("stewardship_hours") or 0)
        stew = round(hours * hourly, 2)
        node_total = round(host_cost + bw + stew, 2)
        participants = int(s.get("participants") or 0) or 1
        out.append({
            "id": s["id"], "label": s["label"], "participants": participants,
            "staff": s.get("staff"), "volunteers": s.get("volunteers"),
            "notes": s.get("notes"),
            "rows": rows, "unpriced_slices": unpriced,
            "commercial_monthly": round(commercial, 2),
            "commercial_annual": round(commercial * 12, 2),
            "commercial_per_participant_year": round(commercial * 12 / participants, 2),
            "node": {"hosts": hosts, "host_total": host_cost, "egress_tb": egress_tb,
                     "bandwidth_cost": bw, "stewardship_hours": hours,
                     "stewardship_cost": stew, "total": node_total},
            "node_annual": round(node_total * 12, 2),
            "node_per_participant_year": round(node_total * 12 / participants, 2),
            "ratio": (round(commercial / node_total, 1) if node_total else None),
        })
    return {
        "assumptions": a, "scenarios": out,
        "ceilings": sc.get("ceilings", []),
        "scale_rates": rates,
        "nonprofit_programs": sc.get("nonprofit_programs", []),
        "counterfactual": sc.get("counterfactual", {}),
        "seat_logic": sc.get("_seat_logic"),
    }


def federation_summary(data):
    """Org-run nodes carrying infrastructure for each other.

    Computes the replication arithmetic and the per-node contribution, using the
    MEASURED shared-asset footprint and the same $/GB rate as the storage slice —
    so 'redundancy is nearly free' is a derivation, not a slogan.
    """
    f = data.get("federation") or {}
    st = data.get("storage") or {}
    per_tb = float(st.get("hardware_cost_per_tb") or 0)
    months = float(st.get("amortization_months") or 36) or 36
    node_rate = per_tb / 1024.0 / months
    hourly = float((data.get("stewardship") or {}).get("hourly_rate") or 0)
    shared = float(f.get("shared_assets_gb") or 0)

    profiles = []
    for p in f.get("profiles", []):
        hw = float(p.get("hardware_monthly") or 0)
        labour = float(p.get("labour_hours") or 0) * hourly
        profiles.append({**p, "labour_cost": round(labour, 2),
                         "total_monthly": round(hw + labour, 2)})

    scen = []
    for s in (f.get("replication") or {}).get("scenarios", []):
        nodes = int(s["nodes"])
        scen.append({**s, "nodes": nodes,
                     "federation_storage_gb": round(shared * nodes, 2),
                     "redundancy_cost_monthly": round(shared * node_rate * nodes, 3),
                     "per_node_cost_monthly": round(shared * node_rate, 3)})

    # the counterfactual that makes the point: the same replicas on S3
    s3_rate = None
    for c in (data.get("comparables") or []):
        if c.get("slice") == "storage" and c.get("vendor") == "Amazon":
            s3_rate = c.get("price")
    s3_redundancy = (round(shared * float(s3_rate) * int((f.get("replication") or {})
                                                        .get("replica_count_independent", 3)), 2)
                     if s3_rate else None)

    return {
        "about": f.get("_about"), "synthesis": f.get("_synthesis"),
        "shared_assets_gb": shared, "asset_note": f.get("_asset_note"),
        "node_rate_per_gb_month": round(node_rate, 5),
        "profiles": profiles, "replication": scen,
        "replica_count_independent": (f.get("replication") or {}).get("replica_count_independent"),
        "replication_thesis": (f.get("replication") or {}).get("_thesis"),
        "replication_note": (f.get("replication") or {}).get("_note"),
        "s3_same_replicas_monthly": s3_redundancy,
        "s3_rate": s3_rate,
        "incentive": f.get("incentive", {}),
        "on_ramp": f.get("on_ramp", []),
        "failure_modes": f.get("failure_modes", []),
        "encryption_reality": f.get("encryption_reality", {}),
        "adversary_doc": f.get("adversary_doc"),
        "adversary_note": f.get("_adversary_note"),
        "universal_core": f.get("universal_core", {}),
        "economic_adversaries": f.get("economic_adversaries", []),
        "convergent_adversaries": f.get("convergent_adversaries", {}),
        "contest_readiness": f.get("contest_readiness", {}),
        "custody_chain": f.get("custody_chain", {}),
        "chilling_effect": f.get("chilling_effect", {}),
        "footprint_attack_surface": f.get("_footprint_attack_surface"),
        "footprints": f.get("footprints", []),
        "footprint_note": f.get("_footprint_note"),
        "food_sector_correction": f.get("_food_sector_correction"),
        "certification_conflict": f.get("certification_conflict", {}),
        "modes": f.get("modes", []),
        "hourly_rate": hourly,
    }


def per_seat_options(comps, slice_name):
    """Verified per-user options in a slice, ascending by price."""
    opts = [c for c in comps
            if c["slice"] == slice_name
            and c["unit"] == "per_user_month"
            and c["status"] == "verified"
            and c.get("price") is not None]
    return sorted(opts, key=lambda c: c["price"])


def tier_per_seat(comps, tier):
    """({slice: comparable}, [slices with no verified price], [slices on fallback]).

    Tier membership is EXPLICIT in the data (`tiers: ["lean","standard"]`), never
    inferred from list position: which product represents 'what a real org of this
    size would actually buy' is an editorial judgement, and the model should show
    the judgement rather than launder it through an index. A slice with no entry
    marked for the tier falls back to its cheapest option AND is reported.
    """
    chosen, missing, fallback = {}, [], []
    for sl in sorted({c["slice"] for c in comps if c["unit"] == "per_user_month"}):
        opts = per_seat_options(comps, sl)
        picks = [c for c in opts if tier in (c.get("tiers") or [])] if opts else []
        if picks:
            chosen[sl] = min(picks, key=lambda c: c["price"])
        elif opts:
            chosen[sl] = opts[0]
            fallback.append(sl)
        else:
            missing.append(sl)
    return chosen, missing, fallback


def per_org_verified(comps):
    """Verified per-org monthly items, deduped by (vendor, product)."""
    seen, rows = set(), []
    for c in comps:
        if c["unit"] != "per_org_month" or c["status"] != "verified" or not c.get("price"):
            continue
        key = (c["vendor"], c["product"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(c)
    return rows


def ticketing(comps, scenario):
    """What a group pays a ticketing platform on ITS OWN ticket revenue, per month."""
    ev = next((c for c in comps
               if c["slice"] == "events_ticketing" and c["status"] == "verified"), None)
    price = float(scenario.get("ticket_price_avg") or 0)
    revenue = float(scenario.get("ticket_revenue_monthly") or 0)
    if ev is None or not price or not revenue:
        return None
    orders = float(scenario.get("avg_tickets_per_order") or 1.0) or 1.0
    tickets = revenue / price
    # per-order processing is paid per order; express it per ticket
    pct = (float(ev.get("pct") or 0) + float(ev.get("order_pct") or 0) / orders) / 100.0
    fee = tickets * (price * pct + float(ev.get("flat_per_ticket") or 0))
    return {
        "vendor": ev["vendor"], "product": ev["product"],
        "pct": ev.get("pct"), "flat_per_ticket": ev.get("flat_per_ticket"),
        "order_pct": ev.get("order_pct"),
        "tickets_per_month": round(tickets, 1),
        "revenue_monthly": round(revenue, 2),
        "fee_monthly": round(fee, 2),
        "fee_pct_of_revenue": round(100.0 * fee / revenue, 1),
        "source": ev.get("source"), "verified_on": ev.get("verified_on"),
    }


def build(data):
    sc, comps = data["scenario"], data["comparables"]

    scope = data.get("slice_scope", {})
    seats = {"members": sc["members"], "organizers": sc["organizers"]}

    def seats_for(sl):
        """Who actually needs a license for this slice.

        NOT every member needs a seat for every tool: a 40-member co-op buys 40
        mailboxes and 40 chat accounts, but maybe 6 CRM seats. Charging all 40 for
        all 8 slices would inflate the commercial column and hand a skeptic the
        argument. `members` is used only where access cannot reasonably be granted
        as a free guest/viewer — identity, mail, chat.
        """
        return seats.get(scope.get(sl, "members"), sc["members"])

    tiers = {}
    for name in TIERS:
        chosen, missing, fallback = tier_per_seat(comps, name)
        rows = []
        for sl, c in sorted(chosen.items()):
            n = seats_for(sl)
            rows.append({"slice": sl, "vendor": c["vendor"], "product": c["product"],
                         "price": c["price"], "scope": scope.get(sl, "members"),
                         "seats": n, "monthly": round(c["price"] * n, 2),
                         "source": c.get("source")})
        tiers[name] = {"chosen": chosen, "rows": rows, "missing_slices": missing,
                       "fallback_slices": fallback,
                       "monthly": round(sum(r["monthly"] for r in rows), 2),
                       "member_slices": sorted(s for s in chosen if seats_for(s) == sc["members"]),
                       "organizer_slices": sorted(s for s in chosen
                                                  if seats_for(s) != sc["members"])}

    org = per_org_verified(comps)
    org_by_slice = {}
    for c in org:
        org_by_slice.setdefault(c["slice"], []).append(c)

    # One credible entry per slice, NOT the cheapest by default: QuickBooks Simple
    # Start at $38 is not a real accounting setup, so taking 'min' there would
    # understate the commercial column. The credible entry is marked explicitly
    # (`mid_tier_pick`) and any slice left to default is reported.
    mid_rows, mid_defaulted = [], []
    for sl, rows in sorted(org_by_slice.items()):
        pick = next((r for r in rows if r.get("mid_tier_pick")), None)
        if pick is None:
            pick = min(rows, key=lambda r: r["price"])
            mid_defaulted.append(sl)
        mid_rows.append(pick)
    mid_tier_monthly = sum(r["price"] for r in mid_rows)

    node = node_monthly(data)
    stew = stewardship_monthly(data)
    rev = data["revenue"]
    inflow = (float(rev.get("member_monthly") or 0) * sc["members"]
              + float(rev.get("group_monthly") or 0) * sc["groups_on_node"]
              + float(rev.get("grant_or_donation_monthly") or 0))

    members_part = float(rev.get("member_monthly") or 0) * sc["members"]
    grants_part = float(rev.get("grant_or_donation_monthly") or 0)
    group_price = float(rev.get("group_monthly") or 0)

    def groups_needed(target):
        need = target - members_part - grants_part
        if need <= 0:
            return 0
        if group_price <= 0:
            return None
        return int(math.ceil(need / group_price))

    return {
        "scenario": sc,
        "illustrative": {"node": bool(data["node"].get("illustrative")),
                         "stewardship": bool(data["stewardship"].get("illustrative")),
                         "revenue": bool(rev.get("illustrative"))},
        "node_monthly": round(node, 2),
        "node_external_monthly": round(node_external_monthly(data), 2),
        "node_external_items": (data.get("node_external") or {}).get("items", []),
        "node_external_illustrative": bool((data.get("node_external") or {}).get("illustrative")),
        "stewardship_monthly": round(stew, 2),
        "irl_infrastructure_only_monthly": round(node, 2),
        "irl_running_monthly": round(node + node_external_monthly(data), 2),
        "irl_total_monthly": round(node + node_external_monthly(data) + stew, 2),
        "revenue_inputs": {"member_monthly": rev.get("member_monthly"),
                           "group_monthly": rev.get("group_monthly"),
                           "grant_monthly": rev.get("grant_or_donation_monthly")},
        "node_inflow_monthly": round(inflow, 2),
        "node_surplus_monthly": round(inflow - node, 2),
        "coverage_of_node_pct": round(100.0 * inflow / node, 1) if node else None,
        "groups_to_cover_node": groups_needed(node),
        "groups_to_cover_total": groups_needed(node + stew),
        "tiers": tiers,
        "mid_tier": {"monthly": round(mid_tier_monthly, 2),
                     "slice_count": len(org_by_slice),
                     "defaulted_slices": mid_defaulted,
                     "items": [{"vendor": r["vendor"], "product": r["product"],
                                "slice": r["slice"], "price": r["price"],
                                "source": r.get("source")} for r in mid_rows]},
        "ticketing": ticketing(comps, sc),
        "maps": per_1k_layer(comps, sc, "per_1k_loads", "map_loads_monthly"),
        "storage_block": storage_summary(data, comps, sc),
        "scale_model": scale_model(data, comps),
        "federation": federation_summary(data),
        "missing": [{"slice": c["slice"], "vendor": c["vendor"], "product": c["product"]}
                    for c in comps if c["status"] != "verified"],
        "derived": [{"slice": c["slice"], "vendor": c["vendor"], "product": c["product"],
                     "basis": c["derived"]} for c in comps if c.get("derived")],
        "caveats": data.get("caveats", []),
        "no_direct_comparable": data.get("no_direct_comparable", []),
        "declared_apps": declared_apps(),
    }


def derive(model):
    """Totals that only exist once the base model is built."""
    tk = model["ticketing"]
    maps_rows = model.get("maps") or []
    # the commercial side gets the CHEAPEST credible option at this volume — at a
    # small co-op's traffic that is usually a free tier, which is the honest result
    maps_cost = min((r["monthly"] for r in maps_rows), default=0.0)
    model["maps_commercial_monthly"] = round(maps_cost, 2)

    # storage + egress: the commercial column takes the cheapest credible option per
    # layer, same rule as maps. The node's own storage is NOT added on the irl side
    # because its disk is already inside the infrastructure line — asymmetric on
    # purpose, and the direction of the asymmetry favours the commercial column.
    S = model.get("storage_block") or {}
    st_rows = [r for r in (S.get("storage") or []) if not r["unpriced"]]
    eg_rows = [r for r in (S.get("egress") or []) if not r["unpriced"]]
    model["storage_commercial_monthly"] = round(min((r["monthly"] for r in st_rows), default=0.0), 2)
    model["egress_commercial_monthly"] = round(min((r["monthly"] for r in eg_rows), default=0.0), 2)

    model["commercial_total_monthly"] = round(
        model["tiers"]["standard"]["monthly"] + model["mid_tier"]["monthly"]
        + (tk["fee_monthly"] if tk else 0.0) + maps_cost
        + model["storage_commercial_monthly"] + model["egress_commercial_monthly"], 2)

    running = model["irl_running_monthly"] or 0.0
    model["ratio_running"] = (f"{model['commercial_total_monthly'] / running:,.0f}×"
                              if running else "n/a")
    infra = model["irl_infrastructure_only_monthly"] or 0.0
    model["ratio_infra_only"] = (f"{model['commercial_total_monthly'] / infra:,.0f}×"
                                 if infra else "n/a")
    full = model["irl_total_monthly"] or 0.0
    model["ratio_full"] = (f"{model['commercial_total_monthly'] / full:,.0f}×"
                           if full else "n/a")
    n = model["groups_to_cover_node"]
    t = model["groups_to_cover_total"]
    gp = model["revenue_inputs"]["group_monthly"]
    def phrase(k):
        if k is None:
            return "undetermined (no group pricing set)"
        if k == 0:
            return "0 extra groups — member contributions alone cover it"
        return f"{k} group(s) at {money(gp)}/mo each"
    model["crossover_node"] = phrase(n)
    model["crossover_total"] = phrase(t)
    return model


# ------------------------------------------------------------------ rendering
def money(v):
    return f"${v:,.2f}" if v is not None else "—"


def rate_money(v):
    """Sub-dollar rates need more decimals than cents, or $0.0022/GB reads as $0.00."""
    if v is None:
        return "—"
    if 0 < abs(v) < 1:
        return "$" + f"{v:.5f}".rstrip("0").rstrip(".")
    return money(v)


def wm(model, *flags):
    """Watermark a number when any contributing input is illustrative."""
    return " *(illustrative)*" if any(model["illustrative"].get(f) for f in flags) else ""


def render(model):
    sc = model["scenario"]
    L = []
    add = L.append

    add("### Cost model — generated")
    add("")
    add(f"Scenario: **{sc['members']} members**, {sc['organizers']} organizers, "
        f"{sc['groups_on_node']} group(s) on the node, "
        f"{money(sc['ticket_revenue_monthly'])}/mo of ticket revenue at "
        f"{money(sc['ticket_price_avg'])}/ticket. Commercial prices are annual-billing "
        f"list prices, verified 2026-09-13.")
    add("")

    add("#### Enterprise tier — per-seat")
    add("")
    add("| Tier | Monthly for the org | Composition | Slices on fallback |")
    add("|---|---|---|---|")
    for name in TIERS:
        t = model["tiers"][name]
        comp = (f"{len(t['member_slices'])} slice(s) × {sc['members']} members + "
                f"{len(t['organizer_slices'])} slice(s) × {sc['organizers']} organizers")
        add(f"| {name} | {money(t['monthly'])} | {comp} | "
            f"{', '.join(t['fallback_slices']) or 'none'} |")
    add("")
    add("Tier membership is set EXPLICITLY per product in `cost-model.data.json` "
        "(`tiers: [...]`), not inferred from list order — which product represents "
        "\"what a member org would actually buy\" is an editorial judgement, and the "
        "model shows it rather than hiding it behind an index. `lean` = cheapest credible "
        "paid tier per slice; `standard` = the tier with real admin/SSO controls (the fair "
        "comparison, since irl.coop ships SSO); `enterprise` = the top published tier or the "
        "negotiated figure.")
    add("")
    add("**Seats are scoped per slice** (`slice_scope`): only identity, mail and chat are "
        "charged to every member — a co-op does not buy 40 CRM seats. Everything else is "
        "counted at the organizer count. Charging all members for all slices would inflate "
        "this column by roughly 3×, which is exactly the kind of number that gets a "
        "comparison dismissed. A slice with no entry marked for a tier falls back to its "
        "cheapest option and is named in the fallback column.")
    add("")

    std = model["tiers"]["standard"]
    if std["rows"]:
        add("**What the `standard` column is made of:**")
        add("")
        add("| Slice | Vendor | Product | /user/mo | Scope | Seats | /mo | Source |")
        add("|---|---|---|---|---|---|---|---|")
        for r in std["rows"]:
            add(f"| {r['slice']} | {r['vendor']} | {r['product']} | {money(r['price'])} | "
                f"{r['scope']} | {r['seats']} | {money(r['monthly'])} | {r['source']} |")
        add(f"| | | | | | **{money(std['monthly'])}** | |")
        add("")

    add("#### Mid-tier — fixed fee, per app")
    add("")
    add("| Slice | Vendor | Product | /mo | Credible entry |")
    add("|---|---|---|---|---|")
    picks = {(i["vendor"], i["product"]) for i in model["mid_tier"]["items"]}
    for it in sorted(model["mid_tier"]["items"], key=lambda i: (i["slice"], i["price"])):
        mark = "✔ selected" if (it["vendor"], it["product"]) in picks else ""
        add(f"| {it['slice']} | {it['vendor']} | {it['product']} | {money(it['price'])} | {mark} |")
    add("")
    add(f"**{money(model['mid_tier']['monthly'])}/mo across "
        f"{model['mid_tier']['slice_count']} subscriptions.** The fee is fixed *per app* — that "
        f"is the mid-tier argument: fixed does not mean one.")
    add("")
    add("The selected entry per slice is marked `mid_tier_pick` in the data, because \"cheapest\" "
        "and \"credible\" are not the same thing: QuickBooks Simple Start at $38/mo is the cheapest "
        "and is not a real accounting setup for a co-op, so Essentials is marked instead."
        + (f" Slices left on the default (cheapest) because no entry is marked: "
           f"{', '.join(model['mid_tier']['defaulted_slices'])}."
           if model["mid_tier"]["defaulted_slices"] else " No slice fell back to the default."))
    add("")

    add("#### Usage-metered layers — tickets and map tiles")
    add("")
    tk = model["ticketing"]
    if tk:
        add(f"**Tickets.** {tk['vendor']} {tk['product']}: {tk['pct']}% + "
            f"{money(tk['flat_per_ticket'])}/ticket + {tk['order_pct']}% per order.")
        add("")
        add(f"On {money(tk['revenue_monthly'])}/mo of ticket revenue "
            f"({tk['tickets_per_month']} tickets), the platform fee is "
            f"**{money(tk['fee_monthly'])}/mo — {tk['fee_pct_of_revenue']}% of the group's "
            f"own revenue**. irl.coop's platform fee on the same revenue: **$0.00**. Card "
            f"processing (~2.9% + $0.30) is common to both worlds and excluded.")
        add("")
        add("The sharpest line in the model: a per-ticket fee **grows with the group's "
            "success**, while the cost of a shared node does not.")
        add("")

    maps_rows = model.get("maps") or []
    if maps_rows:
        vol = maps_rows[0]["volume"]
        add(f"**Map tiles.** At **{int(vol):,} map loads/month** "
            f"(the `scenario.map_loads_monthly` input):")
        add("")
        add("| Vendor | Free allowance | Billable loads | Rate | /mo |")
        add("|---|---|---|---|---|")
        for r in maps_rows:
            add(f"| {r['vendor']} — {r['product']} | {int(r['free']):,} | "
                f"{int(r['billable']):,} | {rate_money(r['rate'])}/1k | {money(r['monthly'])} |")
        add("| irl.coop — self-hosted PMTiles on MinIO | no cap | "
            f"{int(vol):,} | — | $0.00 |")
        add("")
        if model["maps_commercial_monthly"] == 0:
            paid = [r for r in maps_rows if r["monthly"] > 0]
            add(f"**At this volume the cheapest commercial option is inside its free tier**, so a "
                f"co-op comparing on price alone pays $0 either way"
                + (f" — while the pricier option here would be {money(paid[0]['monthly'])}/mo."
                   if paid else ".")
                + " That makes maps a **terms** argument at this scale, not a cost argument: the "
                "tiles cannot be re-priced, rate-limited, or switched off, and there is no card "
                "on file. Say the terms, not the money — a claimed saving here is the easiest "
                "claim in this whole model to disprove.")
        else:
            add(f"Cheapest commercial option at this volume: "
                f"**{money(model['maps_commercial_monthly'])}/mo**; irl.coop: **$0.00** "
                f"(the tiles ride the node's existing storage and bandwidth).")
        add("")

    S = model.get("storage_block") or {}
    if S:
        add("#### Storage — measured, not assumed")
        add("")
        add(f"Measured on the host **{S['measured_on']}** ({S['method']}): "
            f"**{S['measured_total_gb']} GB** under `/opt/app/storage`, of which "
            f"**{S['live_data_gb']} GB is live data** and {S['build_scratch_gb']} GB is build "
            f"scratch plus a duplicate — see the findings below.")
        add("")
        add("| Path | GB | Kind | Detail |")
        add("|---|---|---|---|")
        for b in S["breakdown"]:
            add(f"| `{b['path']}` | {b['gb']} | {b['kind']} | {b.get('detail', '')} |")
        add("")
        add("**Findings from the measurement** (each one is a sentence the video can say):")
        add("")
        for f in S["findings"]:
            add(f"- {f}")
        for u in S["unmeasured"]:
            add(f"- **Not measured:** {u}")
        disk = S.get("disk") or {}
        if disk:
            add(f"- Disk: {disk.get('capacity_gb')} GB, {disk.get('used_gb')} GB used, "
                f"{disk.get('free_gb')} GB free. {disk.get('note', '')}")
        add("")
        add(f"**Node rate: {rate_money(S['node_rate_per_gb_month'])}/GB/mo** "
            f"(hardware ÷ capacity ÷ amortization), so the {S['live_data_gb']} GB of live data "
            f"costs **{money(S['node_storage_monthly'])}/mo**{wm(model, 'node')}. That disk is "
            f"*already inside the infrastructure line above* — this is a RATE comparison, and "
            f"adding it to the totals would be a double count.")
        add("")
        add("| Vendor | Rate | Billable | /mo at the live footprint |")
        add("|---|---|---|---|")
        for r in S["storage"]:
            add(f"| {r['vendor']} — {r['product']} | {rate_money(r['rate'])}/GB | "
                f"{r['billable']} GB | {money(r['monthly'])} |")
        add(f"| irl.coop — MinIO on the node's disk | {rate_money(S['node_rate_per_gb_month'])}/GB | "
            f"{S['live_data_gb']} GB | {money(S['node_storage_monthly'])} |")
        add("")
        add("**Egress, which is where storage bills actually live** — at "
            f"{int(S['egress_volume']):,} GB/mo of transfer:")
        add("")
        add("| Vendor | Free allowance | Billable | Rate | /mo |")
        add("|---|---|---|---|---|")
        for r in S["egress"]:
            rate = "—" if r["unpriced"] else f"{rate_money(r['rate'])}/GB"
            note = " *rate deliberately unquoted*" if r["unpriced"] else ""
            free = f"{r['free']:,.2f} GB" if r["free"] else "none"
            cost = "—" if r["unpriced"] else money(r["monthly"])
            add(f"| {r['vendor']} — {r['product']} | {free} | {r['billable']} GB | "
                f"{rate} | {cost}{note} |")
        add(f"| irl.coop — the node's own uplink | no cap | {int(S['egress_volume']):,} GB | "
            f"— | $0.00 |")
        add("")
        if S["fixed_tiers"]:
            add("**The same bytes as a fixed consumer tier** (sold per account, not per pool):")
            add("")
            add("| Vendor | Tier | Capacity | /mo | Effective |")
            add("|---|---|---|---|---|")
            for t in S["fixed_tiers"]:
                eff = rate_money(t["monthly"] / t["capacity_gb"]) + "/GB" if t["capacity_gb"] else "—"
                add(f"| {t['vendor']} | {t['tier']} | {t['capacity_gb']:,} GB | "
                    f"{money(t['monthly'])} | {eff} |")
            add("")
            add("These are **not** added to the mid-tier column: Google Workspace Business "
                "Standard (already counted at $14/user) includes 2 TB pooled storage per user, so "
                "adding a Drive subscription on top would double-count it.")
        add("")

    add("#### The irl.coop side")
    add("")
    add("| Line | /mo |")
    add("|---|---|")
    add(f"| Infrastructure — node, backups, DNS, amortized hardware | "
        f"{money(model['node_monthly'])}{wm(model, 'node')} |")
    if model["node_external_monthly"]:
        ext_note = " *(illustrative)*" if model["node_external_illustrative"] else ""
        add(f"| Third-party the node cannot make free — carrier numbers, etc. | "
            f"{money(model['node_external_monthly'])}{ext_note} |")
    add(f"| **Running cost (like-for-like)** | **{money(model['irl_running_monthly'])}** |")
    add(f"| Stewardship — a person's time (**not** infrastructure) | "
        f"{money(model['stewardship_monthly'])}{wm(model, 'stewardship')} |")
    add(f"| **Total, honestly stated** | **{money(model['irl_total_monthly'])}** |")
    add("")
    for it in model["node_external_items"]:
        if float(it.get("per_unit_month") or 0) > 0:
            add(f"- *{it['name']}* — {it['count']} × {money(it['per_unit_month'])}/mo. "
                f"{it.get('note', '')}")
    add("")
    add(f"Node inflow at the current pricing inputs: "
        f"**{money(model['node_inflow_monthly'])}/mo**{wm(model, 'revenue')} → "
        f"{'+' if model['node_surplus_monthly'] >= 0 else '−'}"
        f"{money(abs(model['node_surplus_monthly']))}/mo "
        f"({model['coverage_of_node_pct']}% of infrastructure cost covered).")
    add("")
    add(f"- Groups needed to cover **infrastructure**: {model['crossover_node']}")
    add(f"- Groups needed to cover **infrastructure + stewardship**: "
        f"{model['crossover_total']}")
    add("")
    add("Stewardship stays its own line, and third-party costs stay their own line too. A node "
        "that \"pays for itself\" because nobody counts the hours *or* because the phone numbers "
        "were quietly left out is not self-sustaining — it is subsidised by a volunteer and a "
        "credit card, which is the exact failure mode this platform exists to fix.")
    add("")

    add("#### Comparison at a glance")
    add("")
    add("| | /mo | Basis |")
    add("|---|---|---|")
    add(f"| Per-seat stack (`standard`) | {money(std['monthly'])} | "
        f"{len(std['member_slices'])} slices × {sc['members']} members + "
        f"{len(std['organizer_slices'])} slices × {sc['organizers']} organizers |")
    add(f"| Mid-tier fixed fees | {money(model['mid_tier']['monthly'])} | "
        f"{model['mid_tier']['slice_count']} subscriptions |")
    add(f"| Ticketing platform fees | {money(tk['fee_monthly']) if tk else '—'} | "
        f"per-ticket, on the group's own revenue |")
    add(f"| Map-tile fees | {money(model['maps_commercial_monthly'])} | cheapest option at "
        f"{int(sc['map_loads_monthly']):,} loads/mo |")
    add(f"| Object storage | {money(model['storage_commercial_monthly'])} | cheapest vendor at "
        f"{(model.get('storage_block') or {}).get('live_data_gb')} GB live — the node's own disk "
        f"is already inside the infrastructure line |")
    add(f"| Egress | {money(model['egress_commercial_monthly'])} | cheapest option at "
        f"{int(sc['egress_gb_monthly']):,} GB/mo |")
    add(f"| **Commercial total** | **{money(model['commercial_total_monthly'])}** | |")
    add(f"| **irl.coop — infrastructure only** | "
        f"**{money(model['irl_infrastructure_only_monthly'])}**{wm(model, 'node')} | "
        f"one shared node |")
    add(f"| **irl.coop — running cost** | **{money(model['irl_running_monthly'])}** | "
        f"node + the third-party costs it cannot remove |")
    add(f"| **irl.coop — running + stewardship** | "
        f"**{money(model['irl_total_monthly'])}** | one shared node, the person running it, and "
        f"the carrier |")
    add("")
    add(f"Ratio on infrastructure alone: **{model['ratio_infra_only']}**. On the like-for-like "
        f"running cost: **{model['ratio_running']}**. Including stewardship (the honest "
        f"denominator): **{model['ratio_full']}**. The commercial total excludes every slice with "
        f"no verified price, plus local AI, the event bus, and governance — and it *includes* the "
        f"map-tile line at $0, because at this volume that is the truth.")
    add("")

    if model["missing"]:
        add("#### Open items — prices to verify before recording")
        add("")
        add("| Slice | Vendor | Product |")
        add("|---|---|---|")
        for m in model["missing"]:
            add(f"| {m['slice']} | {m['vendor']} | {m['product']} |")
        add("")
        add("These are excluded from every total above. A price with no source and no date "
            "does not go on screen — the `needs_verify` status is what stops this model "
            "quietly turning into marketing.")
        add("")

    if model["caveats"]:
        add("#### Caveats — say these out loud")
        add("")
        add("A comparison with only one side's asterisks is an advertisement. These are the "
            "commercial stack's real advantages and the irl.coop side's real limits; naming "
            "them is what makes the rest of the numbers believable.")
        add("")
        for c in model["caveats"]:
            add(f"- **{c['title']}** — {c['detail']}")
        add("")

    if model["derived"]:
        add("#### Derived figures (assumption stated)")
        add("")
        for d in model["derived"]:
            add(f"- {d['vendor']} {d['product']} ({d['slice']}) — {d['basis']}")
        add("")

    if model["no_direct_comparable"]:
        add("#### No direct comparable")
        add("")
        for n in model["no_direct_comparable"]:
            add(f"- **{n['irl']}** — {n['why']}")
        add("")

    M = model.get("scale_model") or {}
    if M and M["scenarios"]:
        add("### At scale — where the per-seat model stops existing")
        add("")
        add("This is the argument the rest of the model builds toward, and it is **structural, "
            "not financial**: at exactly the size a volunteer movement reaches, the self-serve "
            "product is no longer for sale. A small org rules the attempt out before pricing it "
            "because it has already met this wall once, on some other tool.")
        add("")
        add("#### The ceiling table")
        add("")
        add("| Vendor | Self-serve product | Max users | Above it | Price move |")
        add("|---|---|---|---|---|")
        for c in M["ceilings"]:
            cap = f"{c['max_users']:,}" if c.get("max_users") else "feature-limited"
            up = money(c.get("price_under")) if c.get("price_under") else "—"
            move = f"{up} → {money(c['price_over'])}" if c.get("price_over") else f"{up} → custom quote"
            if c.get("move_note"):
                move += f" ({c['move_note']})"
            add(f"| {c['vendor']} | {c['product']} | {cap} | {c['over_product']} | {move} |")
        add("")
        for c in M["ceilings"]:
            if c.get("note"):
                add(f"- **{c['vendor']}** — {c['note']}")
        add("")
        add("Three independent vendors stop selling at ~250-300 users, and a fourth at ~500. "
            "That is not a coincidence, it is price discrimination by size: per-seat pricing "
            "makes the bill a function of your success, and once the number is big enough to "
            "matter the vendor negotiates instead of publishing. The org experiences this as "
            "*this is not for me* — long before it experiences it as a bill.")
        add("")
        if M.get("seat_logic"):
            add(f"**How seats are counted:** {M['seat_logic']}")
            add("")
        for s_ in M["scenarios"]:
            add(f"#### {s_['label']}")
            add("")
            add(f"{s_['staff']:,} staff, {s_['volunteers']:,} volunteers. "
                + (s_["notes"] or ""))
            add("")
            add("| Slice | Vendor | Product | Rate | Seats | /mo |")
            add("|---|---|---|---|---|---|")
            for r in s_["rows"]:
                add(f"| {r['slice']} | {r['vendor']} | {r['product']} | "
                    f"{rate_money(r['rate'])} | {r['seats']:,} | {money(r['monthly'])} |")
            add(f"| | | | | **{money(s_['commercial_monthly'])}** | |")
            add("")
            if s_["unpriced_slices"]:
                up = ", ".join(f"{u['slice']} ({u['seats']:,} seats)" for u in s_["unpriced_slices"])
                add(f"**Not priced — no verified rate exists at this volume:** {up}. "
                    f"These are sales-led enquiries, not purchases, and they are excluded from "
                    f"the total. The commercial figure below is therefore a **floor**.")
                add("")
            bounded = [r for r in s_["rows"] if r.get("note")]
            if bounded:
                add("**Rate basis — where these figures are bounds, not quotes:**")
                add("")
                for r in bounded:
                    add(f"- **{r['vendor']} {r['product']}** — {r['note']}")
                add("")
            add("| | Commercial | irl.coop node |")
            add("|---|---|---|")
            add(f"| Per month | **{money(s_['commercial_monthly'])}** | "
                f"**{money(s_['node']['total'])}** |")
            add(f"| Per year | **{money(s_['commercial_annual'])}** | "
                f"**{money(s_['node_annual'])}** |")
            add(f"| Per participant / year | {money(s_['commercial_per_participant_year'])} | "
                f"{money(s_['node_per_participant_year'])} |")
            add(f"| Ratio | **{s_['ratio']}×** | |")
            add("")
            add(f"Node side: {s_['node']['hosts']} host(s) at "
                f"{money(s_['node']['host_total'])} + {s_['node']['egress_tb']} TB egress at "
                f"{money(s_['node']['bandwidth_cost'])} + {s_['node']['stewardship_hours']:.0f} "
                f"hrs/mo of stewardship at {money(s_['node']['stewardship_cost'])}.")
            add("")
        if M.get("nonprofit_programs"):
            add("#### Before anyone in the audience says it: the nonprofit programs")
            add("")
            for p in M["nonprofit_programs"]:
                add(f"- **{p['vendor']}** — {p['offer']}. {p['why_it_matters']}")
            add("")
            add("These are real and they must be conceded on camera **before** the argument, not "
                "after. They lower the commercial column for a registered charity. Two limits "
                "keep them from dissolving the point: eligibility is organisational (a movement "
                "may not qualify), and the programs cover **staff accounts** — they do not cover "
                "10,000 volunteer participants.")
            add("")
        if M.get("counterfactual"):
            add(f"#### {M['counterfactual']['title']}")
            add("")
            add(M["counterfactual"]["detail"])
            add("")
        add("**The honest limits of the node at this scale** — state all of them, because a "
            "skeptic will otherwise do it for you:")
        add("")
        add("- **This is not one box.** The host count above is an estimate, not a measured "
            "capacity claim; 10,000 Matrix accounts and 10,000 mailboxes need a real topology, "
            "and mail needs deliverability work (shared-IP reputation, blocklists, SPF/DKIM/DMARC "
            "discipline) that a commercial provider absorbs for you.")
        add("- **The binding constraint is coordination labour, not compute.** Stewardship is the "
            "largest line in every node column above. At 50,000 participants moderation is a "
            "staffed function. The platform makes the software free; it does not make the "
            "moderating free — what it does is make the *decision* to staff it, rather than the "
            "*bill* for it.")
        add("- **Egress is priced as an assumption.** At $"
            f"{M['assumptions'].get('bandwidth_cost_per_tb')}/TB it looks trivial; on a domestic "
            "line it is unmetered and invisible, which means the cost is real and simply not "
            "invoiced. Set it to 0 to model the domestic case and say so.")
        add("")

    F = model.get("federation") or {}
    if F and F.get("profiles"):
        add("### The federation — nodes that carry infrastructure for each other")
        add("")
        add("*Scope: the ECONOMICS and the incentive design. The DNS/edge topology for surviving a "
            "takedown stays parked (`AGENTS.md`) and nothing here requires deciding it.*")
        add("")
        add(F["synthesis"])
        add("")
        add("#### What a node costs, and what it carries")
        add("")
        add("| Tier | Node | Runs | Hardware | Storage | Labour | Total /mo |")
        add("|---|---|---|---|---|---|---|")
        for p in F["profiles"]:
            hrs = f"{p['labour_hours']:.0f} hr" + ("s" if p["labour_hours"] != 1 else "")
            add(f"| {p['tier']} | {p['label']} | {p['apps']} apps | "
                f"{money(p['hardware_monthly'])} | {p['storage_gb']} GB | "
                f"{hrs} | **{money(p['total_monthly'])}** |")
        add("")
        add(f"*Totals include labour at {money(F['hourly_rate'])}/hr; the on-ramp below quotes "
            f"cash only. Note what that does to the cheapest node: an edge node is "
            f"{money(F['profiles'][0]['hardware_monthly'])} of hardware and "
            f"{money(F['profiles'][0]['labour_cost'])} of somebody's attention — "
            f"**even the smallest node is labour-dominated by roughly 8×.** That is the real "
            f"argument for tiering the on-ramp, and it is why the entry point must be ~1 hour, "
            f"not 'a weekend'.")
        add("")
        for p in F["profiles"]:
            add(f"- **{p['label']}** — {p['contributes']} *{p['why_first']}*")
        add("")

        add("#### Redundancy is nearly free — that is the whole argument")
        add("")
        add(F["replication_thesis"])
        add("")
        add("| Nodes holding the assets | Federation storage | Node cost /mo | Resilience | Serving |")
        add("|---|---|---|---|---|")
        for r in F["replication"]:
            add(f"| {r['nodes']} | {r['federation_storage_gb']} GB | "
                f"{money(r['redundancy_cost_monthly'])} | {r['resilience']} | "
                f"{r['serving_multiplier']}× |")
        add("")
        add(f"Each 11.25 GB replica costs **{money(F['replication'][0]['per_node_cost_monthly'])}/mo** "
            f"on hardware the org has already bought — it is idle disk, not a purchase. "
            f"The same three replicas on S3 would be "
            f"**{money(F['s3_same_replicas_monthly'])}/mo** ({rate_money(F['s3_rate'])}/GB). "
            f"The federation's redundancy is not funded; it is the by-product of nodes existing.")
        add("")
        add(F["replication_note"])
        add("")

        add("#### Why an org would run one — the incentive, stated as the design already states it")
        add("")
        add("**What the org gets:**")
        add("")
        for x in F["incentive"].get("for_the_org", []):
            add(f"- {x}")
        add("")
        add("**What the federation gets:**")
        add("")
        for x in F["incentive"].get("for_the_federation", []):
            add(f"- {x}")
        add("")
        add(f"**The proof extension (no new mechanism invented):** "
            f"{F['incentive'].get('the_proof_extension')}")
        add("")

        add("#### The on-ramp — nobody is asked to run a whole stack first")
        add("")
        add("| Phase | What the org takes on | Setup work | Ongoing | Unlocks |")
        add("|---|---|---|---|---|")
        for ph in F["on_ramp"]:
            add(f"| {ph['phase']} | {ph['what']} | {ph['work']} | {ph['cost']} | {ph['unlocks']} |")
        add("")

        add("#### Which pillars can actually be federated — read from the stack, not assumed")
        add("")
        ER = F.get("encryption_reality") or {}
        if ER:
            add(ER["_why_this_is_here"])
            add("")
            add("| Tier | Encrypted with | Protects against | Operator can still read? |")
            add("|---|---|---|---|")
            for t in ER["tiers"]:
                answer = "**no**" if t["solves_federation_custody"] else "yes"
                add(f"| {t['tier']} — {t['name']} | {t['examples']} | {t['protects_against']} | "
                    f"{answer} |")
            add("")
            add("| Pillar | Encrypted today | Federation-safe | Federation target |")
            add("|---|---|---|---|")
            for c in ER["current_state"]:
                enc = c["encrypted"]
                enc_s = "yes" if enc is True else ("n/a — public" if isinstance(enc, str) and enc.startswith("n/a") else "**no**")
                safe = "yes" if c["federation_safe"] is True else "**no — trusted node required**"
                add(f"| {c['pillar']} | {enc_s} | {safe} | {c.get('federation_fix', '—')} |")
            add("")
            if ER.get("doc"):
                add(f"The full fix design — threat model, envelope encryption, erasure-coded "
                    f"sharding, canaries, the client-integrity problem, and what cannot be solved — "
                    f"is `{ER['doc']}`.")
            add("")
            for c in ER["current_state"]:
                if c.get("caveat"):
                    add(f"- *{c['pillar']}:* {c['caveat']}")
            add("")
            add(f"**The design consequence.** {ER['design_consequence']}")
            add("")
            add("**What would have to change to make the stronger claim true:**")
            add("")
            for x in ER["what_would_make_the_claim_true"]:
                add(f"- {x}")
            add("")

        if F.get("adversary_note"):
            add("#### Two adversary classes are universal — so their answer is universal too")
            add("")
            add(F["adversary_note"])
            add("")
            UC = F.get("universal_core") or {}
            if UC:
                add("**The state, in the four modes it actually takes** — the wrong answer differs "
                    "per mode, and confusing them produces the wrong primitive:")
                add("")
                add("| Mode of the state | The answer | Primitive |")
                add("|---|---|---|")
                for sm in UC.get("state_modes", []):
                    add(f"| **{sm['mode']}** | {sm['answer']} | {sm['primitive']} |")
                add("")
                add("**The eight internal tensions that apply to every group, at every size:**")
                add("")
                add("| Tension | Why it is universal | Lever |")
                add("|---|---|---|")
                for t in UC.get("internal_tensions", []):
                    add(f"| **{t['tension']}** | {t['why_universal']} | {t['lever']} |")
                add("")
                if UC.get("_founder_note"):
                    add(UC["_founder_note"])
                    add("")
                add("**Why this collapses the sequencing problem.** Internal tensions vary with "
                    "*size and structure*; external adversaries vary with *politics and activity*. "
                    "Because both universal classes are already present for every group, the core "
                    "is buildable now without choosing pilots:")
                add("")
                for x in UC.get("build_first", []):
                    add(f"- {x}")
                add("")
                add("Sector choice then only decides which **mode** ships next:")
                add("")
                for x in UC.get("then_per_sector", []):
                    add(f"- {x}")
                add("")

        if F.get("economic_adversaries"):
            add("**The economic adversaries** — the class the first version of this analysis "
                "lacked, and the one a food coalition actually faces. An economic adversary "
                "behaves nothing like a state or a hacker:")
            add("")
            add("| # | Adversary | Capability | How it wins |")
            add("|---|---|---|---|")
            for a in F["economic_adversaries"]:
                add(f"| {a['id']} | **{a['name']}** | {a['capability']} | {a['winning']} |")
            add("")

        CA = F.get("convergent_adversaries") or {}
        if CA:
            add("**Adversaries converge without coordinating.** The chain neither adversary has to "
                "plan:")
            add("")
            add(f"`{CA['chain']}`")
            add("")
            for x in CA.get("consequences", []):
                add(f"- {x}")
            add("")

        CR = F.get("contest_readiness") or {}
        if CR:
            add("#### Contest readiness — the capability the sabotage case forces")
            add("")
            add(CR["_why"])
            add("")
            add("| Mode | Question it answers | Consumers |")
            add("|---|---|---|")
            for m_ in CR["modes"]:
                add(f"| **{m_['mode']}** | {m_['question']} | {m_['consumers']} |")
            add("")
            add(CR["unification"])
            add("")
            for x in CR.get("mechanisms", []):
                add(f"- {x}")
            add("")
            if CR.get("note_on_certification"):
                add(CR["note_on_certification"])
                add("")
            add(f"**What it cannot do:** {CR['cannot']}")
            add("")

        CC2 = F.get("custody_chain") or {}
        if CC2:
            add("#### The custody chain — the substrate a contest claim stands on")
            add("")
            add(CC2["_what"])
            add("")
            add(CC2["why"])
            add("")
            add(f"**The trick that keeps it compatible with the footprint axis:** {CC2['the_trick']}")
            add("")
            add(f"**Anchoring:** {CC2['anchoring']}")
            add("")
            add(f"**Why third parties must sign too:** {CC2['evidence_needs_third_parties']}")
            add("")
            pv = CC2.get("proves_vs_not", {})
            if pv:
                add("| Proves | Does **not** prove |")
                add("|---|---|")
                rowsa, rowsb = pv["proves"], pv["does_not_prove"]
                for i in range(max(len(rowsa), len(rowsb))):
                    add(f"| {rowsa[i] if i < len(rowsa) else ''} | "
                        f"{rowsb[i] if i < len(rowsb) else ''} |")
                add("")
                add(f"**The false claim to avoid:** {pv['the_false_claim_to_avoid']}")
                add("")
            add("**Where it earns its keep:**")
            add("")
            for x in CC2.get("use_cases", []):
                add(f"- {x}")
            add("")
            wi = CC2.get("work_item", {})
            if wi:
                add(f"**Work item** — {wi['position']}:")
                add("")
                for i, x in enumerate(wi.get("steps", []), 1):
                    add(f"{i}. {x}")
                add("")
                add(f"*{wi.get('default', '')}*")
                add("")
            if CC2.get("open_decisions"):
                add("**Open decisions:**")
                add("")
                for x in CC2["open_decisions"]:
                    add(f"- {x}")
                add("")

        if F.get("footprints"):
            add("#### Footprint — the third axis, orthogonal to mode")
            add("")
            add(F.get("footprint_note") or "")
            add("")
            add("| Footprint | What an outsider can reconstruct | Who needs it |")
            add("|---|---|---|")
            for x in F["footprints"]:
                add(f"| **{x['footprint']}** | {x['reconstructible']} | {x['fits']} |")
            add("")
            if F.get("footprint_attack_surface"):
                add(F["footprint_attack_surface"])
                add("")
            if F.get("food_sector_correction"):
                add(F["food_sector_correction"])
                add("")

        CC = F.get("certification_conflict") or {}
        if CC:
            add("#### The certification conflict — the second gatekeeper pattern")
            add("")
            add(CC["_what"])
            add("")
            add(f"- **{CC['citation']}:** {CC['requirement']}")
            add(f"- **In practice:** {CC['practically']}")
            add(f"- **The answer:** {CC['the_answer']}")
            add(f"- **Actionable:** {CC['actionable']}")
            add("")

        CE = F.get("chilling_effect") or {}
        if CE:
            add("#### The chilling effect — the harm that lands before any adversary acts")
            add("")
            add(CE["thesis"])
            add("")
            if CE.get("thesis_statement"):
                add(f"> *{CE['thesis_statement']}*")
                add("")
                add(CE["thesis_why"])
                add("")
                for x in CE.get("thesis_lines", []):
                    add(f"- *\"{x}\"*")
                add("")
                add(CE["thesis_measurable"])
                add("")
                add("**The mechanics of the current — each a property of how the market is arranged, not an act by anyone:**")
                add("")
                add("| The default | What it does to a coalition |")
                add("|---|---|")
                for a, b in CE.get("current_defaults", []):
                    add(f"| **{a}** | {b} |")
                add("")
                add(CE["current_no_intent"])
                add("")
                add("**The response — deliberate inversions:**")
                add("")
                add("| The default (the gradient) | The inversion irl.coop makes |")
                add("|---|---|")
                for a, b in CE.get("inversions", []):
                    add(f"| {a} | {b} |")
                add("")
                add(CE["inversions_note"])
                add("")
                add("**How this changes the telling:**")
                add("")
                for i, x in enumerate(CE.get("telling_rules", []), 1):
                    add(f"{i}. {x}")
                add("")
                add("**The series spine — every episode measures the same gradient:**")
                add("")
                for k, v in (CE.get("series_spine") or {}).items():
                    add(f"- **{k}** — {v}")
                add("")
            add("**The tells — say these verbatim; recognition is the whole game:**")
            add("")
            for x in CE.get("tells", []):
                add(f"- *\"{x}\"*")
            add("")
            add(CE["the_swap"])
            add("")
            add(f"**The loop:** {' -> '.join(CE['the_loop'])}")
            add("")
            add(CE["break_point"])
            add("")
            add("| The fear | What it makes organizers do | What irl.coop does | The honest limit |")
            add("|---|---|---|---|")
            for fear, beh, mit, lim in CE.get("fear_table", []):
                add(f"| {fear} | {beh} | {mit} | {lim} |")
            add("")
            add(f"**The comparison rule:** {CE['comparison_rule']}")
            add("")
            add("| Tool | Genuinely good at | What it cannot give you | The honest catch |")
            add("|---|---|---|---|")
            for t, good, cannot, catch in CE.get("tools", []):
                add(f"| **{t}** | {good} | {cannot} | {catch} |")
            add("")
            add("**The five gaps — what NO chat tool can do:**")
            add("")
            for i, x in enumerate(CE.get("the_five_gaps", []), 1):
                add(f"{i}. {x}")
            add("")
            add("**Interoperability stance:**")
            add("")
            for x in CE.get("interop_stance", []):
                add(f"- {x}")
            add("")
            add("**Guardrails — claims we must never make:**")
            add("")
            for x in CE.get("guardrails", []):
                add(f"- {x}")
            add("")

        if F.get("modes"):
            add("#### Group modes — chosen at formation, movable later")
            add("")
            add("| Mode | Fits | Membership visibility | Content | Keys | Blocked by |")
            add("|---|---|---|---|---|---|")
            for m_ in F["modes"]:
                add(f"| **{m_['mode']}** | {m_['fits']} | {m_['membership_visibility']} | "
                    f"{m_['content']} | {m_['keys']} | {m_['blocked_by']} |")
            add("")
            add("A mode change is a first-class operation, not a migration: the union's "
                "`hidden → members` flip at recognition is exactly this. It rotates keys and "
                "re-issues proofs; it does not rewrite history.")
            add("")

        add("#### Failure modes — stated, because they are what actually kills volunteer infrastructure")
        add("")
        for fm in F["failure_modes"]:
            add(f"- **{fm['risk']}** — {fm['why_it_is_the_real_one']}")
            add(f"  *Mitigation:* {fm['mitigation']}")
        add("")

    if model["declared_apps"]:
        add(f"<sub>Cross-check: {len(model['declared_apps'])} apps declared in "
            f"`infra/instances/dev/instance.yaml` — "
            f"{', '.join(model['declared_apps'])}.</sub>")
        add("")
    add("<sub>Regenerate: `python3 infra/scripts/cost-model.py` · "
        "data: `docs/design/cost-model.data.json`</sub>")
    return "\n".join(L)


def render_json(model):
    return json.dumps(model, indent=2, sort_keys=True)


# ------------------------------------------------------------------- injecting
def inject(doc, block, begin=BEGIN, end=END):
    try:
        with open(doc) as fh:
            text = fh.read()
    except OSError as e:
        sys.exit(f"cannot read {doc}: {e}")
    if begin not in text or end not in text:
        sys.exit(f"{doc} is missing the delimiters:\n  {begin}\n  {end}")
    head, rest = text.split(begin, 1)
    _, tail = rest.split(end, 1)
    with open(doc, "w") as fh:
        fh.write(head + begin + "\n" + block.rstrip() + "\n" + end + tail)


def main(argv):
    data_path = DATA
    if "--data" in argv:
        data_path = argv[argv.index("--data") + 1]
    model = derive(build(load(data_path)))
    if "--json" in argv:
        print(render_json(model))
        return
    block = render(model)
    if "--inject" in argv:
        doc = argv[argv.index("--inject") + 1]
        inject(doc, block)
        print(f"injected into {doc}")
        return
    print(block)


if __name__ == "__main__":
    main(sys.argv[1:])
