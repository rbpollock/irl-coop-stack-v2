const { buildPoseidon } = require("circomlibjs");
const fs = require("node:fs");

/**
 * PIN the exact Poseidon hash oracle the treasury tree + spend circuit use.
 *
 * Discovery (recorded in the relayer skill): in circomlibjs 0.1.7
 * `buildPoseidon()` does NOT return an object with `.hash` — it returns a
 * CALLABLE function. Hash by direct invocation:
 *     const poseidon = await buildPoseidon();
 *     poseidon.F.toString(poseidon([a, b]));
 * The circuit's Poseidon(2)(secret,0) === poseidon([secret, 0n]).
 *
 * Asserts the pin against the ceremony witness (nullifierHash). Run after any
 * circomlibjs upgrade or before trusting a relayer-computed root.
 */
const ZK = process.env.ZK_KEY_DIR || "/mnt/storage/zk/keys";

const SECRET = 42424242424242424242n;
// nullifier hash from witness_input.json (spend.circom: nullifierHash = Poseidon(2)(secret, 0))
const WANT = fs.readFileSync(`${ZK}/witness_input.json`, "utf8")
  .match(/"nullifierHash":\s*"(\d+)/)[1];

(async () => {
  const poseidon = await buildPoseidon();
  console.log("typeof result:", typeof poseidon); // should be "function"
  const F = poseidon.F;

  const candidates = [
    ["poseidon([secret,0]) t3",   () => poseidon([SECRET, 0n])],
    ["poseidon([secret,0]) nOut1",() => poseidon([SECRET, 0n], undefined, 1)],
    ["poseidon([0,secret])",      () => poseidon([0n, SECRET])],
    ["poseidon([secret])",        () => poseidon([SECRET])],
    ["poseidon([secret,1])",      () => poseidon([SECRET, 1n])],
    ["poseidon([secret,0,0])",    () => poseidon([SECRET, 0n, 0n])],
  ];
  for (const [name, fn] of candidates) {
    let out;
    try { out = F.toString(fn()); }
    catch (e) { out = "ERR:" + e.message.slice(0, 40); }
    console.log((out === WANT ? "*** MATCH *** " : "              ") + name.padEnd(24) + " -> " + out);
  }
  process.exit(0);
})();