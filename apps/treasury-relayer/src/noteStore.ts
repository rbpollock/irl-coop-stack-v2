import fs from "node:fs";
import path from "node:path";
import { randomBytes } from "node:crypto";
import { buildPoseidonNoteTree, type PoseidonNoteTree } from "./tree";

/**
 * The note ledger — where notes actually come from and live.
 *
 * A NOTE = { secret, amount, commitment, index }. The secret is what the
 * holder keeps; commitment is its public face in the note-tree; nullifier is
 * the spend stamp. Creating a note:
 *    1. generate a fresh cryptographically-random secret (the "how do I prove
 *       I own value" identity of a single treasury note).
 *    2. derive commitment = poseidon([secret, 1]) — the leaf
 *    3. insert into the tree at the next index; the tree advances a root
 *
 * CAPTION NOWHERE: the tree is insert-only (Tornado model); spent leaves stay
 * and the nullifier marks them spent. Thus the stored ledger is append-only
 * keyed by index; `spent` flips when the note's nullifier is sealed on-chain.
 *
 * Persistence: a gitignored JSON file (`NOTE_DIR/ledger.json`) of the note
 * records + a `lastIndex` cursor. On boot, the tree is rebuilt from the stored
 * commitments (so root() is recoverable after restart). The file is the
 * authoring surface — coop-api will delegate note creation here.
 */
export interface Note {
  index: number;
  secret: string; // the note secret (the holder's private material); decimal
  amount: string; // decimal string, the note's value
  commitment: string; // decimal string, the leaf in the tree
  nullifier: string; // decimal string, derived from the secret (spend stamp)
  rootAfter: string; // tree root after this note's insert (the newRoot to commit)
  spent: boolean;
}

export interface NoteStore {
  tree: PoseidonNoteTree;
  notes: Note[];
  lastIndex: number;
  /** create a fresh note (crypto secret) and append it */
  create(amount: bigint): Note;
  /** create a note from a caller-supplied secret (e.g. a treasure-chest note) */
  fromSecret(secret: bigint, amount: bigint): Note;
  get(index: number): Note | undefined;
  list(): Note[];
  markSpent(index: number, nullifier: string): void;
  save(): void; // persist the ledger to disk
}

export interface NoteStoreOptions {
  dir: string; // where ledger.json goes (must be gitignored; holds secrets)
  depth?: number;
}

export async function openNoteStore(opts: NoteStoreOptions): Promise<NoteStore> {
  const tree = await buildPoseidonNoteTree(opts.depth ?? 32);
  const file = path.join(opts.dir, "ledger.json");
  fs.mkdirSync(opts.dir, { recursive: true });

  let ledger: { notes: Note[] } = { notes: [] };
  if (fs.existsSync(file)) {
    try {
      ledger = JSON.parse(fs.readFileSync(file, "utf8"));
    } catch {
      ledger = { notes: [] };
    }
  }

  // Rebuild the tree from the ledger's commitments so root()/next are
  // deterministic across restarts (the tree is derived solely from them).
  for (const n of ledger.notes) {
    tree.insert(BigInt(n.commitment));
  }

  const notes: Note[] = ledger.notes.map((n, i) => ({ ...n, index: i }));

  function persist(): void {
    const payload = { notes, cursor: notes.length };
    const tmp = file + ".tmp";
    fs.writeFileSync(tmp, JSON.stringify(payload, null, 2));
    fs.renameSync(tmp, file);
  }

  function makeNote(secret: bigint, amount: bigint): Note {
    const commitment = tree.commitment(secret);
    const nullifier = tree.nullifier(secret);
    const { index, rootAfter } = tree.insert(commitment);
    const note: Note = {
      index,
      secret: secret.toString(),
      amount: amount.toString(),
      commitment: commitment.toString(),
      nullifier: nullifier.toString(),
      rootAfter: rootAfter.toString(),
      spent: false,
    };
    notes.push(note);
    return note;
  }

  return {
    tree,
    notes,
    lastIndex: notes.length,
    create(amount) {
      // 64 bits of CSPRNG — a uniform secret well under the BN254 field.
      const secret = BigInt("0x" + randomBytes(8).toString("hex"));
      const note = makeNote(secret, amount);
      persist();
      return note;
    },
    fromSecret(secret, amount) {
      const note = makeNote(secret, amount);
      persist();
      return note;
    },
    get(index) {
      return notes[index];
    },
    list() {
      return notes;
    },
    markSpent(index, nullifier) {
      const n = notes[index];
      if (!n) return;
      n.spent = true;
      persist();
      void nullifier;
    },
    save: persist,
  };
}