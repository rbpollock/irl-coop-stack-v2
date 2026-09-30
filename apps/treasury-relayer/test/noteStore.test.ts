import assert from "node:assert/strict";
import path from "node:path";
import os from "node:os";
import fs from "node:fs";
import { openNoteStore } from "../src/noteStore";

/**
 * The note-ledge authoring seam:
 *   1. opening an empty store gives a fresh tree (root = zero-root).
 *   2. create() makes a note: fresh 64-bit secret, derivable commitment +
 *      nullifier, inserts a leaf and advances the root.
 *   3. the store PERSISTS ledger.json; reopening rebuilds the SAME tree
 *      (root equality), so a restart is deterministic.
 *   4. fromSecret honors a caller-supplied secret (treasure-chest path).
 */
async function main() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "relayer-notes-"));
  const store = await openNoteStore({ dir });

  // 1. fresh store
  assert.equal(store.tree.root(), store.tree.zero[32], "empty tree root == zero-root");

  // 2. create one note
  const a = store.create(1_000_000n);
  assert.equal(a.index, 0);
  assert.ok(BigInt(a.secret) > 0n, "secret is a positive number");
  assert.equal(a.commitment, store.tree.commitment(BigInt(a.secret)).toString(),
    "commitment is the poseidon([secret,1]) leaf");
  assert.equal(a.spent, false);
  const root1 = a.rootAfter;
  assert.notEqual(root1, "0", "tree root advanced after one insert");

  // 3. persistence / reopen determinism
  let s2 = await openNoteStore({ dir }); // note the tree is reloaded from ledger
  assert.equal(s2.notes.length, 1, "ledger survived reopen");
    assert.equal(s2.tree.root().toString(), root1, "rebuilt tree root matches persisted root");
    const b = s2.create(2n);
    assert.equal(b.index, 1);
  assert.equal(s2.tree.root().toString(), b.rootAfter, "reopen store root tracked the 2nd insert");

  // 4. fromSecret + markSpent
  let s3 = await openNoteStore({ dir });
  const c = s3.fromSecret(42424242424242424242n, 7n);
  assert.equal(c.index, 2);
  s3.markSpent(c.index, c.nullifier);
  assert.equal(s3.get(c.index)?.spent, true, "marked spent persists");

  // 5. clean up
  fs.rmSync(dir, { recursive: true, force: true });
  console.log("✓ note-store: create/commitment/persist/reopen/fromSecret/markSpent all good");
  process.exit(0);
}
main().catch((e) => { console.error("FAIL:", e.message); process.exit(1); });