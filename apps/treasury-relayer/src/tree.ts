import { buildPoseidon } from "circomlibjs";

/**
 * Real Poseidon note-tree (depth 32, arity 2) — the P3 data plane.
 *
 * Hash oracle PROVEN against the ceremony witness + artifacts:
 *   - commitment leaf: poseidon([secret, 1])   (circuit: outputCommitment)
 *   - nullifier:       poseidon([secret, 0])   (circuit: Poseidon(2)(secret,0))
 *   - internal node:   poseidon([left, right]) (circuit: MerklePathCheck)
 *   - oracle: `buildPoseidon()` returns a CALLABLE; call `poseidon([...])`.
 *
 * Tree model is deliberately the SIMPLE recompute (O(leaves · depth)): the
 * leaves are the inserted commitments and the root is recomputed by folding
 * the up the tree with zero-subtrees, exactly the operation the ceremony's
 * witness generator used (probe: lifting the witness leaf along `zero[]`
 * reproduced the witness root byte-for-byte). Correctness against the ceremony
 * is the requirement, not micro-optimization.
 *
 * GROUND TRUTH (test/noteTree.test.ts): inserting the ceremony's leaf at index
 * 0 MUST return the ceremony's root; after a second insert the root must move.
 */
export interface PoseidonNoteTree {
  depth: number;
  zero: bigint[];
  leaves: bigint[];
  root(): bigint;
  insert(commitment: bigint): { index: number; rootAfter: bigint };
  commitment(secret: bigint): bigint;
  nullifier(secret: bigint): bigint;
}

export async function buildPoseidonNoteTree(depth = 32): Promise<PoseidonNoteTree> {
  const build = await buildPoseidon();
  const nod = (a: bigint, b: bigint) => BigInt(build.F.toString(build([a, b])));

  // zero[i] = Poseidon root of an all-zero subtree of height i.
  const zero: bigint[] = new Array(depth + 1).fill(0n);
  for (let i = 0; i < depth; i++) zero[i + 1] = nod(zero[i], zero[i]);

  const leaves: bigint[] = [];

  function root(): bigint {
    if (leaves.length === 0) return zero[depth];
    // Fold a complete tree level by level; missing siblings fill with zero[h].
    let level = leaves.slice();
    for (let h = 0; h < depth; h++) {
      const pairs = Math.ceil(level.length / 2);
      const up: bigint[] = new Array(pairs);
      for (let i = 0; i < pairs; i++) {
        const left = level[2 * i] ?? zero[h];
        const right = level[2 * i + 1] ?? zero[h];
        up[i] = nod(left, right);
      }
      level = up;
    }
    return level[0];
  }

  function insert(commitment: bigint): { index: number; rootAfter: bigint } {
    const index = leaves.length;
    leaves.push(commitment);
    return { index, rootAfter: root() };
  }

  return {
    depth,
    zero,
    leaves,
    root,
    insert,
    commitment: (secret) => nod(secret, 1n),
    nullifier: (secret) => nod(secret, 0n),
  };
}