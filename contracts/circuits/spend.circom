pragma circom 2.0.0;
include "poseidon.circom";
include "merkle.circom";   // MerklePathCheck — shared by the whole family

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