pragma circom 2.0.0;
include "poseidon.circom";
include "mux1.circom";

// --------------------------------------------------------------------------
// Shared Poseidon Merkle membership. Fixed depth, quadratic-safe branching.
//
// Canonical pattern from spend.circom (where the "T3001 non-quadratic" fix was
// proven): a hand-rolled ternary / (1-s)*a + s*b select is rejected by circom
// 2.x, so we use circomlib's Mux1 (out = (c1-c0)*s + c0) PLUS an explicit
// boolean gate on `sides` (sides*(sides-1)===0). Both are known-safe — this is
// the exact pattern Tornado / ZCash-style note circuits compile against.
//
// If a single tree is shared across every note/badge in the treasury, this IS
// the "root for all of irl.coop". A proof of ANY leaf under the root is a
// proof of membership without revealing which leaf / who / what amount.
// --------------------------------------------------------------------------
template MerklePathCheck(depth) {
    signal input leaf;
    signal input root;
    signal input path[depth];
    signal input sides[depth];

    // sides must be a 0/1 bit (a non-boolean side is spoofable branching)
    for (var i = 0; i < depth; i++) {
        sides[i] * (sides[i] - 1) === 0;
    }

    // pre-allocate components (circom 2.x cannot declare a component in a runtime loop)
    component h[depth];
    component selA[depth];
    component selB[depth];
    for (var i = 0; i < depth; i++) {
        h[i] = Poseidon(2);
        selA[i] = Mux1();
        selB[i] = Mux1();
    }

    signal hash[depth+1];
    hash[0] <== leaf;

    for (var i = 0; i < depth; i++) {
        // side==0: (hash,path); side==1: (path,hash)
        selA[i].c[0] <== hash[i];
        selA[i].c[1] <== path[i];
        selA[i].s   <== sides[i];

        selB[i].c[0] <== path[i];
        selB[i].c[1] <== hash[i];
        selB[i].s   <== sides[i];

        h[i].inputs[0] <== selA[i].out;
        h[i].inputs[1] <== selB[i].out;
        hash[i+1] <== h[i].out;
    }
    root === hash[depth];
}