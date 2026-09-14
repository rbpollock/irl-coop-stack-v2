# Adversary models & sector fit

Status: design · 2026-09-13 · Robbie + Hermes.
Companion to `federation-encryption-and-access.md` — **that doc says *what* can be protected; this
one says *from whom*, and why the answer is different for a food co-op than for an organizing
drive.** Builds on: `group-scoping.md` (§3 privacy tiers — hidden vs members), the worker-union
worked example in `group-model-technical-overview.html` (hidden while organizing → disclosed once
recognized), `group-secret-vault.md` §2.2 (shares held by adversarially-separated parties),
`account-and-key-model.md`, `delegation-and-session-keys.md`.

## 0. Why this analysis is load-bearing

A single default privacy posture is **wrong for almost everyone**. A design that is correct for a
food co-op is dangerous for a pre-recognition union drive; a design that is correct for a rave is
unusable for a credit union. The platform therefore cannot ship one privacy story — it has to ship
**adversary profiles** and let a group choose (and move between) them.

The good news: the shape model already expects this. `governance`, `config`, and `proofs` are three
of the five axes, and the union example already shows a group *changing posture as its adversary
changes* — `hidden` while organizing, flipped to `members` once the bargaining unit is disclosed,
because at that point the employer must know who is covered.

## 0.5 The universal core, and per-sector modifiers on top of it

Robbie's correction, 2026-09-13: **regulatory/state forces are always adversarial, and internal
tensions apply to every sector.** That is right, and it does more work than it first appears —
because if two adversary classes are universal, the design response to them is universal too, and
that means the *core* of the privacy architecture is not sector-conditional at all. Sectors then
become **modifiers**, not separate threat models.

### 0.5.1 The state is always *present* — but sharpening the claim matters

I would state it more precisely than "always adversarial", because the imprecision costs design
quality in both directions:

| Mode of the state | What it does | Wrong answer | Right answer |
|---|---|---|---|
| **Hostile / targeted** | investigates, prosecutes, seizes, surveils | "we'll be transparent" | minimize what exists; nothing to seize; nothing to name |
| **Indifferent** | has authority, no interest | **nothing** (and often over-builds) | nothing — this is where encryption theatre lives |
| **Gatekeeper** | *requires* records: license, audit, filing, election evidence | refuse or over-hide | **selective disclosure** — prove compliance without revealing the underlying data |
| **Dependency** | the group needs a status only the state grants (nonprofit, license, certification) | treat as purely hostile and lose the status | provable compliance, kept separately from member data |
| **Instrument** *(added 2026-09-13)* | acts on information an adversary supplied — a food-safety complaint, an abuse allegation, a competitor's tip, a planted report. **No hostility required; the adversary merely steers it.** | argue innocence with nothing on hand | **contest capability** — be able to prove your own account of events, quickly, without disclosing everything (§0.7) |

The **instrument** mode is the one most often missed, because it looks like an accident. The state
does not have to want to harm you: an adversary who can produce a plausible report has *recruited* a
regulator, an inspector or a prosecutor into the attack for free. That is why the answer is not
"convince them of our good intentions" but "produce our own evidence faster than the allegation
travels" — and it generalizes far past food (an employer's complaint, an abuser's counter-allegation,
a competitor's tip to a licensing board).

The distinction matters because a hostile state is answered by *minimisation* and a gatekeeper state
is answered by *provability*, and confusing them yields the wrong primitive. A regulator that
demands a roster is not attacking you — but it *is* demanding the artifact that must not exist, and
the only good answer is a proof instead of the artifact.

**What is nonetheless universal, and what Robbie's point correctly forces:** the state is the one
adversary that (a) cannot be opted out of, (b) can compel *third parties* — the platform, the node
operator, the ISP, the payment processor, (c) can change its own rules, and (d) may act without the
group ever knowing. That combination means:

> **The platform can never be the trust anchor.** Any design that requires trusting a party the
> state can compel is defeated by definition, whatever sector it is serving.

That is the architectural payoff, and it is why the encryption design in
`federation-encryption-and-access.md` is **not** an edgy-sector feature: threshold keys, client-side
encryption, no master key, no server-side DEK, operator-blind sharding. It is the floor for
everyone, including the food co-op — whose *data* is public but whose *platform* must still not be a
compellable concentration point.

### 0.5.2 Universal internal tensions

Robbie is right that these apply to all sectors. The invariant set — every group, regardless of
mission — is:

| Universal tension | Why it is universal | Design lever |
|---|---|---|
| **The leaving member** (I2) | every group has departures; E2EE cannot retroactively un-share | **epoch keys** |
| **The over-permissioned member** (I1) | access accumulates; roles drift | least privilege, per-object access, no bulk export by default |
| **The group's future self** (I5) | every group eventually has contested succession or a faction | constitutional vs ordinary governance; timelocks |
| **The operator and the platform steward** (I6, I7) | whoever runs the box and ships the code | client-side keys; the platform never holds a DEK |
| **The founder** *(new)* | the person who set it up holds every key, knows every password, and either won't leave or leaves badly | **handover as a documented procedure**; keys held by a threshold, never by a person |
| **The coerced member** (I11) | any member can be pressured; only the *probability* is sector-specific | deniability, compartmentalization, no single person holding everything |
| **The nested boundary** (I10) | any group with sub-groups has a parent/child visibility question | separate DEKs per compartment; no inherited visibility |
| **The wronged member / interested party** *(new)* | disputes are internal; someone with a stake in an outcome is also someone with access | recusal as a governance primitive; conflict-of-interest records in the shape's `governance` axis |

**The founder entry is the same adversary as the node steward's burnout**, one level down: a single
person as the trust boundary. The federation doc's mitigation ("require a named second person per
node") is the group-level mitigation too, and it should be one feature, not two.

### 0.5.3 Why "universal core + modifiers" beats "per-sector"

The two adversary classes vary along **different axes**, which is the real reason the framing works:

| | Varies with | Consequence |
|---|---|---|
| **Internal tensions** | **size and structure** — a 5-person group has ~no capture or infiltration risk; a 500-person one has a lot | escalate controls as the group grows, not as its mission changes |
| **External adversaries** | **politics and activity** — legal, illegal, or merely visible | switch mode by what the group *does*, not how big it is |

Which produces the payoff: **the universal core is buildable now and is justified for every sector**,
so the sequencing problem I flagged in §9.1 dissolves. You do not have to pick pilots before
building vault non-custody, epoch keys, non-enumeration and selective disclosure — those are the
floor. Sector choice then only decides *which modes* get built next, and that decision can wait.

## 0.6 The third axis: footprint legibility

**Robbie's correction, 2026-09-13, and it overturns my first pass.** I assigned food co-ops to "Open
mode" on the reasoning that their roster and calendar are public. That conflated two different
things:

- **The projection** — what the storefront tells the world: hours, offerings, the market schedule,
  the produce list. Genuinely public, and it *must* be findable or nobody shops.
- **The store of record** — supplier terms, volumes, land pipeline, capital plan, price agreements,
  membership, who is behind on what. **Operational, competitive, sometimes life-safety-sensitive.**

A food co-op is **retail-facing public and operationally private** — which is a different shape, not
an open one. And the threat is not hypothetical: food is a market where the incumbent is enormous,
the margins are thin, and a coalition that reaches scale **disrupts the status quo in a way that
invites adversarial behaviour**. Competition from a monopoly is not "a competitor"; it is an actor
that can pick apart a smaller coalition link by link.

So **footprint legibility is a second, orthogonal choice**, independent of how members and content
are protected:

| Footprint | What an outsider can reconstruct | Fits |
|---|---|---|
| **Published** | the front, deliberately: offerings, hours, contact — *never the member roll, volumes, terms, or pipeline* | customer-facing co-ops, events |
| **Sparse** | the fact that a group exists and roughly what it does; nothing that maps the network | most operational groups |
| **Unreadable** | not even a reliable count | identity-threatened coalitions, supply-chain organisers, hostile jurisdictions |

**The rule this produces:** a co-op has a **published front and an unreadable back**, and the front
must be a *projection* — rendered from the back, sparse by construction — not a second copy of the
truth that someone remembers to curate. A "public" storefront that lists your members, your
suppliers or your growth plan is not public-spirited; it is competitive intelligence, and for an
identity-threatened group it is worse than that.

This is also the axis on which the *food coalition* and the *union* meet: both must be findable by
the people they serve and illegible to the party that would rather they did not exist.

### 0.6.1 Two principles the footprint axis adds

1. **No single counterparty can reconstruct the coalition.** Least privilege is not sufficient —
   the *combination* of parties must not jointly reconstruct the network. If the certifier, the
   lender and the distributor each hold a partial view, the union of those views *is* the map, and
   each one of them is acquirable (E16). This is anti-correlation, and it is the same discipline as
   erasure sharding one layer up: **shard the view, not just the storage.**
2. **The group is not one perimeter.** Members inside the *same* group can have radically different
   exposure — a Somali farmer, a Black farmer and a white ally in the same co-op do not face the
   same adversary, and a single "group visibility" setting exposes the most vulnerable member to the
   least-threatened one's risk. The unit of control is therefore **per-member, per-pair
   visibility** — which the seat primitive already models ("per-(user, group) persona: roles,
   *visibility*"). **Reuse it as an exposure control, not just a role label.**

## 0.7 Convergent adversaries, and the capability the sabotage case forces

**Robbie's extension, 2026-09-13** — E18 planting negative coverage and committing subtle sabotage.
It matters because it puts one adversary in three domains at once, and because of what it does to the
*chain* of adversaries.

### 0.7.1 Adversaries converge without coordinating

E15 (the incumbent) and E18 (the violent actor) want the same outcome — a discredited, shut-down,
displaced co-op — and their methods compose into a chain neither has to plan:

```
subtle sabotage  →  food-safety incident  →  regulatory action  →  market vacancy the incumbent fills
```

Three things follow. **The incident *is* the attack**: a contamination event destroys a food business
permanently even when the sabotage is later proven, so detection is not the goal — *contestability*
is. **The state can be recruited as an unwitting step** (that is the instrument mode, §0.5.1): a
plausible complaint enlists an inspector at no cost to the adversary. And the **weakest link is
whoever has the least to lose** — often a counterparty, not a member.

### 0.7.2 The capability: contest readiness

The analysis has so far assumed the group's problem is *being read*. This adds the opposite problem:
**being accused.** Same primitive family, used in the other direction:

| Mode | Question it answers | Consumers |
|---|---|---|
| **Selective disclosure** (positive) | "how are we doing?" | certifiers, funders, regulators, members |
| **Contest readiness** (defensive) | "what actually happened, and who held custody?" | an inspector, a court, an insurer, the press |

Both are the same machinery — **commitments + proofs + tamper-evident logs + selective reveal** — and
together they **resolve the "cannot be exculpated" trade (§5.8) in the good direction.** The false
choice was between *unreadable* and *able to prove*. The real answer is **commit now, reveal later,
selectively**: the record is provable without being readable, and the group chooses when and to whom.
That is a strictly better answer than either horn, and it applies to the entheogenic practitioner and
the sabotage victim alike.

### 0.7.3 Tamper-evidence beats tamper-resistance

You cannot stop someone poisoning an input, spoiling storage, or damaging equipment. You *can* make it
detectable, attributable and **provable**:

- **A signed custody chain** — who signed for what, when — which is the already-designed
  hash-chained ledger tier, applied to *goods* instead of credits. **Now specified in
  `custody-chain-and-contest-kit.md`**, because it is the first primitive here that must be
  *built* rather than productised: a contest claim without a tamper-evident record behind it is
  only a promise.
- **Counter-signed receipts between counterparties**, so a disputed delivery carries two signatures
  and neither party can alter it alone.
- **Anchored records** — periodic anchors to an external witness, so a later claim that "the log was
  edited" is checkable rather than a matter of trust.
- **An incident log shaped as evidence** (timestamps, custody, signatures, no retroactive edits) —
  because it will be read by an insurer, a regulator, or a court, not by the group.

Note what this does to the certification conflict of §5.9: the traceability records the co-op is
*obliged* to keep become its **defence kit** — provided the records are the co-op's own and
tamper-evident, rather than only living in the certifier's file.

### 0.7.4 A second argument for the footprint axis: illegibility is attack-surface reduction

§0.6 justified sparse footprints as a *disclosure* control. The sabotage case adds an independent
reason: **if an outsider cannot see who supplies what, they cannot choose the highest-leverage node
to attack.** Illegibility does not merely limit exposure — it removes targets. A coalition whose
supply chain is unreadable is harder to interdict *and* harder to discredit by proxy.

### 0.7.5 What the platform cannot do: stop a lie

Narrative attack is mostly outside the platform's power, and the honest answer is a short list:

- **Own a channel** (the published front) so the group is not speaking only through other people's
  platforms, on other people's terms.
- **Pre-position signed, dated statements of fact** — certifications, inspections, provenance policy,
  membership counts — so a smear campaign meets verifiable priors instead of a vacuum. This is the
  cheapest defensive work available and almost nobody does it before the attack.
- **Produce evidence fast** — the contest kit above.

And then say plainly: **a lie is a lie.** Cryptography makes your own account checkable; it does not
make people believe you. Selling a reputation-defence product as a technical guarantee would be the
same category of dishonesty as selling disk encryption as protection from the operator.

## 1. The adversary taxonomy

Two axes: **position** (internal ↔ external) and **what they want** (read it / prove it / disrupt it
/ coerce someone into giving it).

### 1.1 Internal adversaries

| # | Adversary | Capability | What "winning" looks like | Design lever |
|---|---|---|---|---|
| I1 | Over-permissioned member | legitimate read access, curiosity or carelessness | screenshots, forwarded exports | least privilege by role; per-object access; no bulk export by default |
| I2 | **Leaving member** | retains every key/share they ever held | reads content created *after* they left, unless keys rotate | **epoch keys** — E2EE cannot retroactively un-share |
| I3 | Minority faction (< k) | some shares, some access | cannot decrypt; pressure and attrition are the real costs | threshold; then it is a *social* problem, not a cryptographic one |
| I4 | k collusion | full group authority | by design, this is the group acting, not an attack | none — choose k so that set *is* the legitimate authority |
| I5 | **The group's own future self** | a faction legally captures the Safe and rewrites roles | legitimate-looking governance that hands over the archive | constitutional vs ordinary governance; timelocks; rotation gated at a higher threshold than role changes |
| I6 | **Node operator / steward** | root on the box: disks, DB, memory of anything it runs | reads everything the node holds | the entire encryption design — their position is the backend's position |
| I7 | **Platform steward — including me** | deploys code, holds platform secrets, can push an update to every node | reads everything by shipping a change | **the platform must never be *required* for trust**: no master key, no server-side DEK, client-verified builds |
| I8 | Peer node operator | holds your replica or erasure share | reads your shard, maps your data | erasure coding + ciphertext-only; shares of ciphertext are inert |
| I9 | Contractor / temporary staff | short, specific access | long memory of a short window | scoped grants with expiry (ERC-7715 already models this) |
| I10 | Nested sub-group boundary | is a parent member but not a child member | reads across a boundary that was supposed to be a wall | separate DEKs per sub-group; no inherited visibility |
| I11 | **Coerced member** | an authorized insider acting *as someone else's instrument* (partner, employer, immigration status, police pressure) | legitimate access used under duress | deniability, compartmentalization, and *not* holding everything in one person's hands |

**I7 deserves the uncomfortable sentence:** a platform whose security story is "trust the people who
run it" has not solved anything, it has relocated the problem. You are the adversary to design
against, and the design already accommodates that: *steward, not root* is a cryptographic property
before it is a governance one.

### 1.2 External adversaries

| # | Adversary | Capability | Why it is different from the others | Sector where it dominates |
|---|---|---|---|---|
| E1 | **The intimate adversary** | physical device access, knows the person, may be the reason they joined | a *relationship*, not an attack — no patch fixes it | mutual aid, community safety, healing justice |
| E2 | **Infiltration** (agent or informant) | gets legitimately authorized, then reports | **cannot be stopped cryptographically — only blast-radius limited** | unions, rave, entheogenic, animal/environmental, activism |
| E3 | **Law enforcement / state** | subpoena, warrant, seizure, gag order, prosecution | shapes architecture more than any other actor | entheogenic, unions, mutual aid, hostile jurisdictions |
| E4 | **Regulators & professional bodies** | require records, audit, license | **wants your data for compliance, not for punishment — the hardest case, because refusal is itself a violation** | credit unions, alt-health, childcare, food |
| E5 | Civil litigants | discovery in a dispute | converts your data into someone else's evidence | unions (employer litigation), housing, worker co-ops |
| E6 | **The employer** | surveillance, captive-audience meetings, retaliation | the adversary the union exists to face | worker unions |
| E7 | Hostile press / opposition research | publicising what it obtains | leak → reputational, not legal | advocacy, edgy subcultures |
| E8 | Doxxers, harassers, trolls | aggregation from public fragments | does not need a breach at all — **the crowd is the source** | rave, activism, alt-health |
| E9 | Attacker for profit | ransomware, credential stuffing, crypto theft | indifferent to your cause; volume attacks | every group with money (credit unions, treasuries) |
| E10 | **Platform/dependency adversaries** | cloud ToS, payment processors, app stores, DNS | an *availability* attack, not a breach: you keep the data and lose the ability to serve it | everyone; acute for edgy sectors |
| E11 | Funders | grant conditions demanding beneficiary lists and impact metrics | **creates the dangerous list in the name of accountability** | mutual aid, nonprofits, healing justice |
| E12 | **The crowd** | screenshots, a phone seized at the door, an overheard conversation, someone proud of their involvement | the leak is voluntary and human | rave, mutual aid, community safety |
| E13 | Supply chain | a compromised dependency or image tag | scales with the federation | everyone |
| E14 | **The physical world** | warrant executed at an event, venue security, police at the door, a raid | the breach happens where the keys are | rave, entheogenic, community safety |

### 1.3 Four adversaries the food-sector analysis forced (added 2026-09-13)

Robbie's correction on food co-ops exposed a gap: the taxonomy had no first-class **economic**
adversary, and an economic adversary behaves nothing like a state or a hacker.

| # | Adversary | Capability | What "winning" looks like |
|---|---|---|---|
| E15 | **The corporate incumbent** | outspends you by orders of magnitude; can buy your distributor, your processor, your landlord, your certifier; can price below cost until you fold; can litigate to exhaust you | reads your footprint — supply chain, land pipeline, volumes, membership, capital plan — and interdicts the weakest link before you reach scale |
| E16 | **The chokepoint holder** (distributor, co-packer, certifier, lender, landlord, insurer) | sits between you and the market; is *not* a member; is often acquirable or pressure-able | sees the whole network by virtue of its position, and can be bought, leaned on, or subpoenaed |
| E17 | **The asset speculator** | reads public land records, outbids, holds, waits | buys the land under the farms the co-op depends on and sets the rent |
| E18 | **The identity-based violent actor** | **three domains at once: physical** (harm to people, property, crops, water), **informational** (planted negative coverage, rumours, manufactured scandal), **supply-chain** (contamination and subtler poisoning-the-well acts — bad inputs, spoiled storage, tampered equipment) | the group is discredited, shut down, or displaced — *the incident is the attack, and the reputational damage persists even when the sabotage is proven* |

**E18 changes a property from "preference" to "safety".** Where the group itself is targeted for
who its members are, **non-enumeration is not a privacy setting — the roster is a physical-safety
artifact.** That is a stronger claim than §3's "who needs it most" column implies, and it should be
reflected in defaults: a group whose members are identity-threatened should not be *offered* a
published roster as the easy path.

**E15/E16/E17 are why "footprint legibility" is a required property** (§0.6), and why the answer is
not merely "encrypt the data" — a monopoly does not need to break your encryption when it can count
your trucks, your acreage, and your filings.

## 2. The four trust boundaries

Every group's profile is really a statement about *which boundary carries the weight*.

| Boundary | The question | Sectors where it dominates |
|---|---|---|
| **Member ↔ member** | can a member see who else is in, and what they said? | community safety, healing justice, therapy groups, 12-step-adjacent |
| **Member ↔ group** | can the group see what a member did or received? | mutual aid (recipients), union drives, alt-health (patients) |
| **Group ↔ operator** | can whoever runs the box read or be forced to reveal? | unions, rave, entheogenic, hostile jurisdictions |
| **Group ↔ world** | can an outsider enumerate, link, or prove membership? | advocacy, doxxing targets, hostile jurisdictions |

Note that **only the third boundary is about code the platform writes.** The first, second and
fourth are about defaults, proofs and metadata — which is why non-enumeration and selective
disclosure are *product* primitives, not encryption trivia.

## 3. The properties, and the tensions between them

| Property | Means | Who needs it most |
|---|---|---|
| **Confidentiality** | content unreadable to the operator | everyone hosting other people's data |
| **Non-enumeration** | the membership and beneficiary lists cannot be listed | mutual aid, unions in formation, entheogenic |
| **Unlinkability** | donor↔recipient, member↔attendance cannot be joined | mutual aid, community safety |
| **Deniability** | a member can plausibly deny membership | unions in formation, rave, hostile jurisdictions |
| **Auditability** | the group *can prove* something to an outsider | credit unions, unions (post-recognition), alt-health, funders |
| **Availability / liveness** | the service is up when it matters | everyone, acutely at events |
| **Recoverability** | the data survives a member losing a key | non-technical groups, healthcare |
| **Accountable anonymity** | unattributable to the world, attributable to the group | mutual aid, community safety, entheogenic |

**The spine of this whole document:** *Auditability* and *Recoverability* fight *Confidentiality* and
*Non-enumeration*. Every sector sits somewhere different on that line, and the platform's job is to
make the trade-off **explicit and per-group** rather than silently uniform.

## 4. Sector matrix — read each row as *the universal core plus* what this sector adds

Every row below assumes the universal core of §0.5: the state as a permanent constraint, the eight
invariant internal tensions, and the platform-never-as-trust-anchor floor. What differs is the
**#1 additional adversary**, the existential artifact, and the properties that dominate.

### A. Mutual aid & solidarity economies (incl. Food Sovereignty, Relational Infrastructure)

- **#1 adversary:** the intimate one (E1) and the state's ability to map beneficiaries (E3). An
  abusive ex finding an address through a delivery list is not a theoretical threat model.
- **Existential data:** who received what, where, when — plus immigration status and benefit
  eligibility.
- **Law requires:** in most places, very little beyond basic nonprofit accounting. *This sector has
  the most freedom to encrypt and typically doesn't know it.*
- **Needs:** non-enumeration, unlinkability (donor↔recipient), deniability, and delivery logistics
  that don't leak addresses.
- **Cannot be given:** protection from a recipient who tells their own story; and a *funding* story
  usually demands exactly the list that must not exist (E11) — solved by proofs, not rosters.
- **Sentence that lands:** *"No one can produce a list of who got help."*

### B. Worker unions & labour (Solidarity Economies)

- **#1 adversary:** **the employer** (E6), with civil litigation (E5) close behind — and the
  employer holds most of the leverage before recognition.
- **Existential data:** the pre-recognition roster of who signed a card. This is the one document
  that can get people fired.
- **Law requires:** after recognition, plenty — dues records, duty-of-fair-representation records,
  election evidence. **Statutory duties fight end-to-end encryption**, and this is not avoidable.
- **The stage flip is the design:** `hidden` while organizing → `members` once recognized (already
  modelled in the group overview). The platform's value is concentrated in the *pre-recognition
  window*, and it should be honest that it shrinks afterwards.
- **Needs:** accountable anonymity during formation, audits that work afterwards, a strike fund with
  hard guards (already designed: N-of-M, timelock, circuit breaker).
- **Cannot be given:** a defence against the employer already knowing who works there; retroactive
  concealment of a roster the group later disclosed by law.
- **Sentence that lands:** *"Organize before anyone can be listed."*

### C. Socially conscious / advocacy / civic engagement

- **#1 adversary:** opposition research (E7), doxxing (E8), and deplatforming (E10).
- **Existential data:** strategy, donor identities, unredacted meeting notes.
- **Law requires:** campaign-finance and lobbying disclosure in many jurisdictions — i.e. **partial
  public disclosure is the point**, which makes selective disclosure the central primitive.
- **Needs:** least privilege on strategy, strong export control, and a public/private split that is
  explicit rather than accidental.
- **Cannot be given:** protection from your own press release; the crowd is the source (E12).
- **Sentence that lands:** *"The strategy is not in the same place as the newsletter."*

### D. Community safety (violence interruption, harm response, "Community Safety" vertical)

- **#1 adversary:** the state (E3) *and* the community's own need for confidentiality in every
  direction — including toward the person who caused harm.
- **Existential data:** who was involved, what happened, who was told. A leaked accountability
  process endangers the harmed, the harmer, and the process.
- **Law requires:** varies wildly; often the group is doing something a state agency would rather
  handle, which is itself a legal exposure.
- **Needs:** the strongest compartmentalization on this list, member↔member confidentiality,
  accountable anonymity, and *durable* availability during an emergency.
- **Cannot be given:** safety at the physical layer, or protection from an insider who is part of
  the incident.
- **Sentence that lands:** *"The people in the room can't see the room's records."*

### E. Rave, subculture, cultural power (Cultural Power vertical)

- **#1 adversary:** law enforcement **at the event** (E14/E3) plus infiltration (E2) and the crowd
  (E12). The realistic breach is a device seized at the door with the passcode given under pressure.
- **Existential data:** the guest list, the venue, the money, and any identity that links a person
  to a substance.
- **Law requires:** licensing, fire code, and (for the edgy end) nothing you would want in writing.
- **Needs:** the **Deniable** profile (§6) — short-lived keys, no persistent plaintext on members'
  devices, rapid rotation, and *no central roster to seize*.
- **Cannot be given:** protection for a device seized with the owner present. Device policy is the
  member's, and the platform should say so plainly rather than implying otherwise.
- **Sentence that lands:** *"There is no list to seize."*

### F. Entheogenic medicine, alternative health, Healing Justice

- **#1 adversary:** **the regulator** (E4) — drug enforcement, medical boards, licensing — which is
  categorically different from a police adversary, because *refusing to produce records is itself a
  violation*.
- **Existential data:** patient identities and session records. These are health data about people
  doing something that is criminal in some jurisdictions and licensed in others.
- **Law requires:** in licensed contexts, records sufficient to demonstrate competent practice —
  which means the practitioner may *need* to be able to read their own notes, and may need to
  produce them in a disciplinary proceeding.
- **The sharpest trade-off in this document:** **a system that cannot be read cannot be
  exculpated.** The same unreadability that shields a patient from prosecution denies the
  practitioner the records that prove they practised properly. Any claim to the contrary is
  dishonest, and the honest options are: per-practitioner encryption (the practitioner, not the
  platform, holds the key — so they can choose to disclose), or accepting that this sector is
  in tension with the design.
- **Needs:** per-practitioner key custody, patient-side non-enumeration, and a selective-disclosure
  primitive ("I hold records meeting standard X" without producing the records).
- **Sentence that lands:** *"The practitioner holds the key — not the platform, not the node, and not
  the group."*

### G. Land, housing & community land trusts (Land Back)

- **#1 adversary:** the state's own title records and the speculator (both external), plus **the
  faction that would sell** (I5).
- **Existential data:** beneficial ownership, occupancy, who is behind on what.
- **Law requires:** titles, trustees, filings — the most *publicly* recorded sector here.
- **Needs:** the interesting inverse — this sector needs **auditability and durability** more than
  secrecy, plus anti-capture governance (constitutional clauses, timelocks, supermajority to
  alienate property).
- **Sentence that lands:** *"The rule that says you can't sell it is written where you can't edit
  it."*

### H. Credit unions, financial co-ops, treasuries

- **#1 adversary:** **the regulator** (E4) and the fraudster/attacker (E9).
- **Law requires:** essentially everything — KYC, transaction records, audit trails. **This is the
  sector where end-to-end encryption is largely incompatible with the legal obligation**, and the
  design should say so rather than pretend otherwise. Its proper answer is auditable governance,
  hard treasury guards and on-chain transparency for the parts that must be provable — not
  operator-blind storage.
- **Sentence that lands:** *"Your books are provable without being readable by the platform."*

### I. Food, farming & supply coalitions (Food Sovereignty, Ecological Repair)

**Rewritten 2026-09-13 after Robbie's correction.** This sector was previously filed as "practical
commons → Open mode". That was wrong in a specific and instructive way: it conflated *public
storefront* with *public organisation*.

- **#1 adversary:** **the corporate incumbent** (E15), acting through **chokepoints it can buy**
  (E16 — the distributor, the co-packer, the certifier, the lender) and **land** (E17). The state is
  present as always, but here it is usually the indifferent or gatekeeper mode, not the hostile one.
- **Existential data:** supplier identities and terms, volumes, the land pipeline, the capital plan,
  price agreements, and — where members are identity-threatened — **the membership itself, which is a
  physical-safety artifact** (E18).
- **Three distinct sub-cases, which is why one label never fit:**

| Sub-case | What it needs | Why |
|---|---|---|
| **The adoption / disruption co-op** (farms, food hubs, processing) | footprint **Sparse or Unreadable**; supplier and volume data encrypted; no published growth trajectory | reaching scale in a thin-margin market *is* the provocation. An incumbent reads acreage, trucks and filings — not your database |
| **The identity-threatened coalition** (e.g. Somali, Latino, Black farmers organising together) | footprint **Unreadable**; non-enumeration as *safety*, not preference; **per-member exposure tiers** | the group is a target *because of who is in it*. A shared "group visibility" setting exposes the most vulnerable member to the least-threatened one's risk |
| **The input-refusers** (no synthetic inputs, no commercial fertiliser) | the certification conflict below | their practice is documented to a certifier, and that documentation is the map |

- **The certification conflict — the food-sector twin of the union's statutory duty.**
  Certified organic production is *required* to be traceable: 7 CFR Part 205 requires a certified
  operation to "fully disclose all activities and transactions… in sufficient detail as to be
  readily understood and audited", with records that "span the time of purchase or acquisition,
  through production, to sale or transport and be traceable back to the last certified operation",
  retained ~five years and re-tested annually by a **traceback exercise** (finished product → each
  ingredient) plus a **mass-balance exercise** (quantities reconcile).
  **So the map exists by law** — and that is not a reason to abandon the goal, it is the clearest
  possible case for **selective disclosure**: prove traceability *to the certifier*, without the map
  being readable by anyone else who can obtain it.
  **A concrete, actionable consequence:** the *choice of certifier is a privacy decision.* A private
  accredited certifier holds your traceability records privately (and can be subpoenaed); a **state**
  certification program is a public agency, so its records may be subject to public-records requests
  — which hands the coalition's supply map to whoever files. Say that in the onboarding flow.
- **Needs:** footprint control, per-pair visibility, unlinkable procurement (the supply-chain form of
  donor↔recipient unlinkability), and the anti-correlation principle of §0.6.1 — *no single
  counterparty may reconstruct the coalition.*
- **Cannot be given:** a legal form that guarantees a private member roll (entity-formation and
  director records are public in many jurisdictions — choose the form for its disclosure profile);
  protection from a member who markets their own involvement; and immunity from predatory pricing,
  which is an economic problem, not an information one.
- **Sentences that land:**
  - to a food hub: *"They can count your trucks. They can't read your plan."*
  - to an identity-threatened coalition: *"Nothing here can be used to find your members."*
  - to a certified operation: *"You can prove it to the certifier without handing the map to anyone else."*

**The general lesson this sector taught the whole document:** *"the data is public"* is almost never
true of an organisation. It is usually true of its **projection**. Ask which one you mean.

### J. Food co-ops, childcare, tool libraries, practical commons (Relational Infrastructure)

- **#1 adversary:** health/safety regulators, insurers, internal sloppiness — genuinely the mildest
  profile here.
- **Needs:** the **Published footprint** and a plaintext roster *for the parts that are meant to be
  public* (the volunteer rota, the tool catalogue, the calendar) — with the operational layer
  (insurance, finances, incidents, staff matters) encrypted as a matter of course.
- **The correction, kept:** encrypting a volunteer rota is still a category error. What was wrong was
  generalising that to *the whole sector* — a tool library and a farming coalition are not the same
  threat profile, and this row exists only for the former.
- **Sentence that lands:** *"Nobody pays per seat for a volunteer rota."*

### K. Faith, language & cultural communities in hostile jurisdictions (Healing Justice, Cultural Power)

- **#1 adversary:** the state (E3) *and* intra-community coercion (I11) — the group may be the
  safest place for a person and the most dangerous if the wrong member reads it.
- **Needs:** deniable membership, non-enumeration, offline-first behaviour, and no dependency on
  infrastructure inside the hostile jurisdiction (E10).
- **Sentence that lands:** *"Nothing you store here can be used to name you."*

## 5. The recurring conflicts, stated once each

1. **Compliance vs confidentiality → proofs, not plaintext.** The answer to "the regulator needs
   records" is rarely "decrypt everything". It is *selective disclosure*: prove dues collected ≥ X,
   prove funds reached aid, prove a facilitator's certification, prove a count. The primitives are
   already designed (`zk-badges`, coverage proofs, commitments) — **this is the most valuable missing
   product primitive on the list**, because it unblocks unions, alt-health, funders and credit
   unions at once.
2. **Onboarding vs infiltration → you cannot win, you can only shrink the blast radius.** Vouching,
   progressive disclosure, compartmentalized sub-groups with separate DEKs. An authorized informant
   with legitimate access to everything defeats every cryptographic control, and the design should
   say so rather than hint otherwise.
3. **Revocation is not retroactive.** Epoch keys: rotate the DEK, and new content is safe from a
   departing member — old content is not, and never will be. A group that needs more than that needs
   a different architecture, not a better key.
4. **The operator under pressure is the point, not a side case.** For unions, rave and entheogenic
   groups the operator is *personally* exposed. End-to-end encryption protects the operator from
   being coerced as much as it protects the member — which is a genuine recruitment argument for
   running a node.
5. **The endpoint is the weakest link, and it is not the platform's to fix.** A phone seized at a
   rave, a laptop in a raid, an abusive partner with the passcode. Platform E2EE does not reach
   that, and implying it does is the most common dishonest claim in privacy marketing.
6. **A group's own future is an adversary.** Governance capture is a *legitimate-looking* path to the
   archive: constitutional vs ordinary decisions, timelocks, and DEK rotation at a higher threshold
   than role changes.
7. **The funder's data clause creates the danger.** Grant reporting that demands beneficiary lists
   manufactures exactly the artifact that must not exist. Offer counts, ranges and proofs as the
   deliverable instead.
8. **Deniability vs exculpation.** See sector F. Some groups need the ability to *prove* their
   innocence later, which is in direct conflict with nobody being able to read anything. Choose
   deliberately, per group, and say which one you chose.
9. **Certification requires the map you are trying not to have.** The clearest second instance of #1,
   and the one that proves the pattern is structural rather than a union quirk: organic certification
   obliges a producer to keep auditable records traceable from input purchase through to sale, for
   years, tested annually by a traceback exercise (7 CFR Part 205). A coalition that wants its supply
   chain illegible to an incumbent is *legally required* to document exactly that chain for a
   certifier. **The only honest resolution is selective disclosure: prove it to the certifier,
   publish it to no one.** And an actionable consequence falls straight out of it — **the certifier
   is a privacy decision**: a private accredited certifier holds those records privately; a *state*
   program is a public agency whose records may be obtainable by anyone who files. That belongs in
   the onboarding flow, stated plainly, because a co-op that picks a certifier for cost alone may
   hand its supply map to its competitor.
10. **"The data is public" is almost never true of an organisation — only of its projection.** The
   error this document made in its first version (assigning food co-ops to Open mode) is the same
   error each group makes about itself. Ask which one is meant: the front, or the store of record.

## 6. Group profiles — mode × footprint, chosen independently

Two orthogonal choices. **Mode** governs how members and content are protected; **footprint**
governs how legible the organisation is to an outsider. A group picks one of each, and can move both
as its situation changes.

**Mode:**

| Mode | Who it fits | Membership visibility | Content | Keys |
|---|---|---|---|---|
| **Open** | tool libraries, childcare rotas, public events — *the parts that are meant to be public* | public roster | plaintext (a public good) | none |
| **Guarded** | mutual aid, advocacy, practical programs, **food hubs and adoption co-ops** | in-group only, non-enumerable to outsiders | client-side encrypted | per-group DEK, k-of-n to members |
| **Compartmented** | unions in formation, community safety, peer support, **identity-threatened coalitions** | commitment-only — not even the platform can enumerate | encrypted per sub-group, **separate DEKs per compartment** | epoch keys; rotation on membership change |
| **Deniable** | rave, subculture, hostile jurisdictions, entheogenic | no central roster; membership proven on demand | encrypted; no persistent plaintext on member devices | short-lived keys, frequent epoch rotation |

**Footprint** (§0.6) — chosen on the same screen, because for many groups it matters more:

| Footprint | Reconstructible from outside | Who needs it |
|---|---|---|
| **Published** | the deliberately sparse front: offerings, hours, contact | retail-facing co-ops, public events |
| **Sparse** | existence and rough purpose; nothing that maps the network | most operational groups, food hubs |
| **Unreadable** | not even a reliable count | identity-threatened coalitions, supply-chain organisers, hostile jurisdictions |

**Two rules that follow:**

- **The footprint applies to the *projection*, never the store of record.** A Published front is
  rendered from the encrypted back and stays sparse by construction — a front page listing members,
  suppliers or growth plans is not public-spirited, it is competitive intelligence.
- **Mode and footprint are not a ladder.** A food hub wants a *Published* front and an *Unreadable*
  back; a union in formation wants both unreadable; a tool library wants both open. Choosing the
  wrong combination is how a group either exposes itself or makes itself unfindable to the people it
  exists to serve.

The move between profiles is a first-class operation, not a migration: **the union's
`hidden → members` flip at recognition is exactly this**, and the group overview already describes
it. A profile change rotates keys and re-issues proofs; it does not rewrite history.

## 7. What we cannot protect, by sector — and should say so

| Sector | The honest gap |
|---|---|
| Mutual aid | a recipient who tells their own story; the crowd is the leak (E12) |
| Unions | the employer knows who works there; post-recognition rosters are public *by law* — the platform's protection is a *window*, not a vault |
| Community safety | nothing at the physical layer, and nothing against an insider who is part of the incident |
| Rave | a device seized with the passcode given under pressure |
| Entheogenic / alt-health | a participant searched at an event or a border; and the "cannot be exculpated" trade (§4F, §5.8) |
| Credit unions | end-to-end encryption is largely incompatible with the legal duty to keep records — say it rather than promise around it |
| Everyone | the group's own decision to disclose; a member who is authorized *and* hostile; and the fact that availability is not a cryptographic property |

## 8. What this changes in the build order

**Revised by §0.5.** The universal core is justified for every sector, so it is no longer gated on
choosing pilots:

**Build first, for everyone (the universal core — no pilot decision needed):**
1. **The vault fix (custodial → non-custodial)** — the precondition for all of it. A platform-held
   key defeats every mode in §6 and contradicts §0.5.1's floor, so nothing below matters until the
   vault stops holding a key it has no business holding.
2. **Non-enumeration as a first-class property alongside encryption.** For mutual aid, unions,
   advocacy, community safety and alt-health the *list* is more dangerous than the *content* —
   and the state-as-permanent-constraint argument makes the list dangerous for every group that has
   one. That is `group-scoping.md` §3 tier 2 (commitment-based, "hidden-from-platform") —
   designed and deferred. **Promoted.**
3. **Selective-disclosure proofs.** They are what makes the gatekeeper mode of the state survivable:
   prove dues collected ≥ X, prove funds reached aid, prove a certification, prove a count. The
   primitives exist (`zk-badges`, coverage proofs, commitments); they need productising.
4. **Contest readiness — commit now, reveal later** (§0.7.2), **with its substrate**: the
   counter-signed **custody chain** (`custody-chain-and-contest-kit.md`). Every group can be falsely
   accused, so an evidence-ready, tamper-evident record of *your own* events is a universal
   capability — and a contest claim with no record behind it is only a promise. This is the first
   primitive in the cluster that must be **built** rather than productised, and it turns the
   "cannot be exculpated" trade (§5.8) from a painful choice into a non-choice: the record is
   provable without being readable.
5. **Epoch keys** — required by the leaving member (I2), which is universal, not sector-specific.

**Then, per sector (only decides which mode ships next):**
6. **Footprint control — the third axis, and the food-sector correction.** A **sparse projection**
   rendered from an encrypted store (Published front / Unreadable back), plus **per-pair visibility**
   so a member's exposure is their own decision. This is §0.6, it is cheap, and for food coalitions
   and identity-threatened groups it matters more than content encryption.
6. **Compartmented mode** — unions in formation, community safety, peer support, identity-threatened
   coalitions.
7. **Deniable mode** — rave, subculture, hostile jurisdictions, entheogenic.
8. **Open mode, scoped correctly** — tool libraries, childcare rotas, public events. Ship it as a
   deliberate *absence* of privacy machinery **for the parts that are meant to be public**, and stop
   generalising it to whole sectors. A tool library and a farming coalition are not the same threat
   profile; the first version of this document made exactly that error and it is worth keeping
   visible as a warning.

## 9. Open decisions for Robbie

1. ~~Which two or three sectors are the first pilots?~~ **Resolved by §0.5: build the universal core
   first** — it is justified for every sector, so the pilot choice no longer gates the work. What is
   still open: **which mode ships next**, once the core exists. Compartmented (unions in formation,
   community safety) is the higher-value one, because it is the mode whose absence is currently a
   safety problem rather than a convenience problem.
2. **Is non-enumeration a platform guarantee or a per-group setting?** A guarantee is a much
   stronger claim, and much harder to walk back.
3. **Entheogenic/alt-health:** do we accept the "cannot be exculpated" trade explicitly, or offer a
   per-practitioner key custody model (which is the honest version of "we can't read it, but you
   can")?
4. **Credit unions:** do we simply not serve them, or serve them with an explicitly
   *auditable-not-blind* posture? Pretending E2EE fits them is worse than declining.
5. **A warrant-canary posture?** The platform could publish a signed, regular attestation that it
   has received no demands. Cheap, and it makes compulsion visible.
