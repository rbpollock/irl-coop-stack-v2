import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { buildPoseidonNoteTree } from "../src/tree";

/**
 * The NOTE-TREE ground-truth test: reproduce the ceremony's root.
 *
 * The ceremony's first spend proved a leaf under a root; the witness
 * recorded that leaf (index 0, all sides 0). If our accumulator +
 * hash convention are right, inserting that SAME leaf at index 0 must
 * recompute the SAME root the proof committed. That is the definitive
 * "the relayer's newRoot is the real tree" signal.
 */
const ZK = process.env.ZK_KEY_DIR ? path.resolve(process.env.ZK_KEY_DIR) : "/mnt/storage/zk/keys";

async function main() {
  const w = JSON.parse(fs.readFileSync(path.join(ZK, "witness_input.json"), "utf8"));
  const leaf = BigInt(w.leaf);
  const wantRoot = BigInt(w.root);
  const wantNullifier = BigInt(w.nullifierHash);
  const secret = BigInt(w.secret);

  const tree = await buildPoseidonNoteTree(32);

  // 1. commitment/nullifier derivation must match the circuit's witnesses.
  //    (the nullifier is poseidon([secret,0]) — PROVEN in the earlier probe)
  assert.equal(tree.nullifier(secret), wantNullifier, "nullifier must match ceremony witness");
  console.log("✓ nullifier(secret) == witness nullifier");

  // 2. Inserting the witness leaf (index 0) must reproduce the witness root.
  const { index, rootAfter } = tree.insert(leaf);
  assert.equal(index, 0, "first leaf goes at index 0");
  assert.equal(rootAfter, wantRoot, "inserting witness leaf at 0 must yield the ceremony root");
  console.log("✓ inserting witness leaf at index 0 yields root == ceremony root");
  console.log("  root  ", rootAfter.toString());
  console.log("  leaf  ", leaf.toString());

  // 3. A second, fresh note also yields a moving, coherent root.
  const secret2 = 987654321987654321n;
  const c2 = tree.commitment(secret2);
  const r2 = tree.insert(c2);
  assert.notEqual(r2.rootAfter, wantRoot, "a second leaf must move the root");
  console.log("✓ a second leaf moves the root (index", r2.index, "->", r2.rootAfter.toString(), ")");

  // 4. root() of the tree after 2 inserts must equal the stored r2.rootAfter.
  assert.equal(tree.root(), r2.rootAfter, "root()/insert must agree");
  console.log("✓ insert(rootAfter) == tree.root()");

  process.exit(0);
}
main().catch((e) => { console.error("FAIL:", e.message); process.exit(1); });