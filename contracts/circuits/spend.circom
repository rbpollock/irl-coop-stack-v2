pragma circom 2.0.0;
include "poseidon.circom";
include "mux1.circom";

// --- Poseidon Merkle membership (fixed depth), using circomlib Mux1 ----------
template MerklePathCheck(depth) {
    signal input leaf;
    signal input root;
    signal input path[depth];
    signal input sides[depth];

    // sides must be a bit (a non-boolean side is spoofable branching)
    for (var i = 0; i < depth; i++) {
        sides[i] * (sides[i] - 1) === 0;
    }

    // pre-allocate components (circom 2.x cannot declare a component in a loop)
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

// --- the v0 spend proof ---
template Spend() {
    // public
    signal input root;          // on-chain merkle root the note lives in
    signal input nullifierHash; // pool marks this spent

    // private
    signal input leaf;          // the note commitment in the tree
    signal input secret;        // note secret (to derive nullifier + ownership)
    signal input path[32];      // merkle path
    signal input sides[32];
    signal input secretOut;     // new note's secret (output)

    // 1. existence: leaf is under `root`
    component m = MerklePathCheck(32);
    m.leaf <== leaf;
    for (var i = 0; i < 32; i++) {
        m.path[i] <== path[i];
        m.sides[i] <== sides[i];
    }
    m.root <== root;

    // 2. nullifier freshness: nullifierHash = Poseidon(secret, 0)
    component nil = Poseidon(2);
    nil.inputs[0] <== secret;
    nil.inputs[1] <== 0;
    nullifierHash === nil.out;

    // 3. output note is a real note: outputCommitment = Poseidon(secretOut, 1)
    component outc = Poseidon(2);
    outc.inputs[0] <== secretOut;
    outc.inputs[1] <== 1;
    signal output outputCommitment;
    outputCommitment <== outc.out;
}

component main = Spend();