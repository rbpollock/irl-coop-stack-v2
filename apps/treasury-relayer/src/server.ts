import fs from "node:fs";
import path from "node:path";
import Fastify from "fastify";

// The treasury relayer — OFF-CHAIN proof gate for the shielded pool.
//
// A standalone internal app (mirror of peer_xyz_payments' rail): it is the
// only process that runs the Groth16 pairing check and it owns the note
// ledger (the authoring surface where notes are created).
//
// RELAYER MODEL (plan §8/§10): a permissionless relayer verifies spend proofs
// off-chain and submits a SEAL to the pool — the pool records the nullifier
// + the Poseidon root. This service is that relayer. The pool-wire step
// (spend tx) is gated on a deploy; here it runs the proof gate AND the
// note-authoring API.

import { verifyRelay, type RelayParams, type RelayOutcome } from "./verify";
import { openNoteStore, type NoteStore, type Note } from "./noteStore";

const PORT = Number(process.env.RELAYER_PORT ?? 3020);
const KEY_PATH = process.env.ZK_KEY_DIR
  ? path.join(process.env.ZK_KEY_DIR, "spend_vk.json")
  : "/mnt/storage/zk/keys/spend_vk.json";
// Dir for the note ledger (SECRETS). Gitignored; default under the stack.
const NOTE_DIR = process.env.NOTE_DIR ?? "/mnt/storage/treasury-notes";

async function main(): Promise<void> {
  const fastify = Fastify({ logger: false });

  // Load the verification key once at startup (fail loud if the ceremony key
  // is missing — the relayer is not provisioned).
  let vk: unknown;
  try {
    vk = JSON.parse(fs.readFileSync(KEY_PATH, "utf8"));
  } catch (e) {
    console.error(`[treasury-relayer] cannot load spend_vk.json at ${KEY_PATH}:`, (e as Error).message);
    process.exit(1);
  }

  // The note ledger (secrets). Rebuilt from disk on boot so the tree root is
  // deterministic across restarts. A corrupt dir is a real sectional failure.
  let noteStore: NoteStore;
  try {
    noteStore = await openNoteStore({ dir: NOTE_DIR, depth: 32 });
  } catch (e) {
    console.error(`[treasury-relayer] cannot open note store at ${NOTE_DIR}:`, (e as Error).message);
    process.exit(1);
  }

  fastify.get("/health", async () => ({
    ok: true,
    vk_loaded: !!vk,
    vk_path: KEY_PATH,
    note_dir: NOTE_DIR,
    notes: noteStore.notes.length,
    root: noteStore.tree.root().toString(),
  }));

  // -------- note authoring seam --------
  // POST /notes { amount }  -> create a fresh note, insert into the tree,
  // return the note (secret, commitment, nullifier, rootAfter).
  // Reading the secret back is the point: the caller (coop-api) shows the
  // secret to the member; the RELAYER keeps it only to rebuild the tree.
  fastify.post("/notes", async (request, reply) => {
    const body = (request.body ?? {}) as Record<string, unknown>;
    const amount = body.amount;
    if (amount === undefined || typeof amount !== "string" && typeof amount !== "number") {
      return reply.code(400).send({ ok: false, error: "amount (string|number) is required" });
    }
    const amt = BigInt(typeof amount === "string" ? amount : Math.trunc(Number(amount)));
    const note: Note = noteStore.create(amt);
    return reply.code(201).send({ ok: true, note });
  });

  // optional: create from an explicit secret (treasure-chest / migration)
  fastify.post("/notes/fromSecret", async (request, reply) => {
    const body = (request.body ?? {}) as Record<string, unknown>;
    const secret = body.secret as string;
    const amount = body.amount as string;
    if (!secret || !amount) {
      return reply.code(400).send({ ok: false, error: "secret and amount are required" });
    }
    const note = noteStore.fromSecret(BigInt(secret), BigInt(amount));
    return reply.code(201).send({ ok: true, note });
  });

  // GET /notes -> the ledger (index, commitment, amount, spent; NOT the secret
  // secret — that's private. Reveal only structure.)
  fastify.get("/notes", async () => {
    const safe = noteStore.notes.map((n) => ({
      index: n.index,
      amount: n.amount,
      commitment: n.commitment,
      nullifier: n.nullifier,
      spent: n.spent,
      rootAfter: n.rootAfter,
    }));
    return { ok: true, notes: safe, count: safe.length, root: noteStore.tree.root().toString() };
  });

  // GET /notes/:index/secret -> the NOTE'S SECRET (the redeem material). This
  // is intentionally a plain, unauthenticated dev endpoint; production wants
  // the caller to be the member (coop-api) presenting identity.
  fastify.get("/notes/:index", async (request, reply) => {
    const { index } = request.params as { index: string };
    const i = Number(index);
    const note = noteStore.get(i);
    if (!note) return reply.code(404).send({ ok: false, error: `no note at index ${i}` });
    return { ok: true, note };
  });

  // -------- proof gate (unchanged) -----
  fastify.post("/relay", async (request, reply) => {
    const body = (request.body ?? {}) as Record<string, unknown>;
    const root = body.root as string;
    const outputCommitment = body.outputCommitment as string;
    const inputNullifier = body.inputNullifier as string;
    const proof = body.proof as RelayParams["proof"];

    if (!root || !outputCommitment || !inputNullifier || !proof) {
      return reply.code(400).send({ ok: false, error: "root, outputCommitment, inputNullifier and proof are required" });
    }
    // Validate the proof SHAPE before the expensive verifier (a malformed
    // proof is a 400, not a 500). snarkjs wire form has trailing 1s.
    const pA = Array.isArray(proof.pi_a) && proof.pi_a.length > 2;
    const pB = Array.isArray(proof.pi_b) && proof.pi_b.length > 2 &&
      Array.isArray(proof.pi_b[0]) && proof.pi_b[0].length > 1 &&
      Array.isArray(proof.pi_b[1]) && proof.pi_b[1].length > 1;
    const pC = Array.isArray(proof.pi_c) && proof.pi_c.length > 2;
    if (!pA || !pB || !pC) {
      return reply.code(400).send({ ok: false, error: "malformed proof (expected snarkjs wire form: pi_a*, pi_b[2][2], pi_c*)" });
    }

    const p: RelayParams = { root, outputCommitment, inputNullifier, proof };
    let r: RelayOutcome;
    try {
      r = await verifyRelay(vk, p);
    } catch (err) {
      return reply.code(400).send({ ok: false, error: `proof rejected: ${(err as Error).message}` });
    }
    if (!r.ok) {
      return reply.code(400).send({ ok: false, error: r.reason ?? "proof rejected" });
    }

    return reply.send({
      ok: true,
      relay: { root, outputCommitment, inputNullifier },
      note: "proof verified off-chain; ready to submit to the pool seam",
    });
  });

  await fastify.listen({ port: PORT, host: "0.0.0.0" });
  console.log(`[treasury-relayer] listening on :${PORT} (notes: ${noteStore.notes.length})`);
}

main().catch((err) => {
  console.error("[treasury-relayer] fatal:", err);
  process.exit(1);
});