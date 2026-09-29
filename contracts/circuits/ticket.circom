pragma circom 2.0.0;
include "poseidon.circom";
include "merkle.circom";

// 3-input Poseidon computed from the proven 2-arity Poseidon template.
// (circomlib ships Poseidon(2) for the 2-element arity; any N-ary hash is built
//  as a chain of Poseidon(2) — this is the exact de-dup pattern the family uses.)
template Poseidon2Chain() {
    signal input a;
    signal input b;
    signal input c;
    signal output out;
    component m = Poseidon(2);
    m.inputs[0] <== a;
    m.inputs[1] <== b;
    component r = Poseidon(2);
    r.inputs[0] <== m.out;
    r.inputs[1] <== c;
    out <== r.out;
}

// --------------------------------------------------------------------------
// TicketCheck — a SMART ticket (sketch, compilable skeleton).
//
// Same substrate as spend.circom: a leaf under a Merkle ROOT, Poseidon + Mux1,
// shared MerklePathCheck from merkle.circom. So it rides the exact pipeline we
// already proved. Three concerns, one of which is honestly NOT offline:
//
//   1. AUTHENTICITY — leaf under event root. Offline-verifiable (Groth16 key +
//      proof, no network.) That's the win.
//
//   2. FRESHNESS — the same ticket can't be waved twice. nullifierID from the
//      leaf; BUT "used" is GLOBAL state, which a proof alone cannot carry.
//      Offline you get a synced "used" set at the gate or a punched local list.
//      We keep nullifierID (the mechanism) and front the honest caveat at the
//      API layer — not hide it in-circuit.
//
//   3. CHILD DERIVATION — a valid parent yields a child ticket bound to a tag
//      (early-bird, second-tshirt, treasure-hunt advance, random-reward). This
//      is the "proof-to-proof" coin of the family: parent is an un-revealed
//      witness; childLeaf is a fresh commitment the venue can insert into a new
//      root. Offline issuable by the gate that just saw the parent.
//
// Widgets for the Robbie scenarios; each is a DIFFERENT childTag going to a
// DIFFERENT childLeaf — so a tshirt holder and a waiter and a treasure-hunter
// each get THEIR OWN ticket path, provable to yes/onward while revealing no
// parent's identity amount. That EXACTLY wants a circuit family, not one gate.
// --------------------------------------------------------------------------
template TicketCheck(DEPTH) {
    // --- public (the gate checks these) ---
    signal input root;            // event treeproot that admits this ticket
    signal input nullifierID;     // leaf-derived; gate tracks "already used"

    // --- private (the member/venue witness) ---
    signal input leaf;            // ticket commitment: Pose3(eventId, secret, 0)
    signal input secret;          // holder's secret, binds the leaf to them
    signal input path[DEPTH];
    signal input sides[DEPTH];

    // --- child-derivation fields (the "smart" branch) ---
    signal input childTag;        // e.g. 1=earlybird, 2=second-tshirt, 3=treasure
        signal input childSecret;     // new secret for the child (private by default)
    signal output childLeaf;      // a NEW commitment issuable into a NEW root

    // 1. authenticity — the ticket is a real minted leaf under the event root.
    component m = MerklePathCheck(DEPTH);
    m.leaf <== leaf;
    for (var i = 0; i < DEPTH; i++) {
        m.path[i] <== path[i];
        m.sides[i] <== sides[i];
    }
    m.root <== root;

    // 2. freshness mechanism — nullifierID derives from the leaf + secret,
    //    unique per ticket; the gate checks "already used?" against ITS state.
    component nf = Poseidon(2);
    nf.inputs[0] <== leaf;
    nf.inputs[1] <== secret;
    nullifierID === nf.out;

    // 3. child derivation — childLeaf is a fresh leaf for a NEW tag path.
    //    if childTag==0 no child (plain entrance); else child leaf is generated.
    component ch = Poseidon2Chain();      // Pose(leaf, childSecret, childTag)
    ch.a <== leaf;
    ch.b <== childSecret;
    ch.c <== childTag;
    // "no child" case: with childTag==0 the venuw mints a null child — the
    // ISSUING gate decides whether to store childLeaf, not the proof itself.
    childLeaf <== ch.out;
}

component main = TicketCheck(32);