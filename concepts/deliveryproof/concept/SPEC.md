# DeliveryProof — Specification (v0.9.1)

DeliveryProof gates payment settlement on **verified delivery** of a digital deliverable. This document specifies the three core objects, the `Verifier` and `RailAdapter` interfaces, the settlement state machine, the verifier tiers, and the extension points for real rails and proof systems.

Status: **v0.9.1 local hardening build for the OSS library**. The wire
shapes and interfaces below are the intended-stable surface; the in-repo
implementations are reference implementations unless explicitly marked mock or
interface-only. Core wire records still use protocol version
`deliveryproof/0.4-jcs1`: v0.9 added integration helpers, and v0.9.1 corrected the
canonicalizer to emit JCS text directly (fixing integer-like-key ordering such as
`{"10":1,"2":2}`) without changing the wire profile — string-keyed records are
byte-identical to before.

Production-readiness boundary: v0.9.1 targets the objective-verification library
only. It does not ship a hosted SaaS, custody layer, real payment rail adapter,
legal/tax certification, formal third-party audit, or production Tier-B proof
system. A real deployment additionally needs a non-custodial production rail
adapter, production key management, operator security review, and any required
attested Tier-B verifier.

The in-repo mock rail is a reference state machine, not production money movement.
The durable rail demonstrates local WAL recovery and idempotency, not universal
exactly-once settlement across external payment networks. Tier-B interface
descriptors are descriptors only; the runnable `signed-oracle` proves only that an
allowed attester signed a bound statement.

---

## 1. Core objects

All objects are plain JSON. Hashes are lowercase hex SHA-256 over an RFC-8785-style JSON Canonicalization Scheme (JCS) encoding (see §6). Signatures are Ed25519, base64-encoded. Core wire records carry `protocolVersion` so future incompatible canonicalization or schema changes are explicit.

### 1.1 DeliveryContract

The agreement: what is bought, the predicate that defines "delivered", the price, the SLA, and the rail.

| Field | Type | Description |
|-------|------|-------------|
| `protocolVersion` | string | Protocol/canonicalization version, currently `deliveryproof/0.4-jcs1`. |
| `id` | string | Unique contract id. |
| `buyer` | string (`keyId`) | Buyer identity = `keyId` of buyer public key. |
| `seller` | string (`keyId`) | Seller identity = `keyId` of seller public key. |
| `intent` | string | Human-readable statement of what is being bought. |
| `deliverableType` | string | Type tag for the deliverable (e.g. `"array"`, `"json"`, `"document"`). |
| `predicate` | object | The delivery predicate. See below. |
| `predicate.kind` | `'schema' \| 'hash' \| 'testsuite' \| 'transcript' \| 'dataset' \| 'api-response' \| 'document' \| 'compose' \| 'signed-oracle'` | Selects the verifier. |
| `predicate.params` | object | Verifier-specific parameters. See §2. |
| `price` | object | `{ amount: number, currency: string }`; `amount` must be positive and finite. |
| `sla` | object | `{ deadlineMs: number }` — delivery deadline. |
| `refundRule` | string | Human-readable refund policy. |
| `railId` | string | Identifier of the settlement rail to use. |
| `nonce` | string | Anti-replay nonce; binds evidence/transcripts to this contract. |
| `createdAt` | number | Unix epoch ms. |

### 1.2 DeliveryEvidence

The produced deliverable, bound to the contract.

| Field | Type | Description |
|-------|------|-------------|
| `protocolVersion` | string | Protocol/canonicalization version. |
| `contractId` | string | The `DeliveryContract.id` this evidence answers. |
| `nonce` | string | Must equal the contract `nonce`. |
| `output` | any | The actual deliverable. |
| `outputHash` | hex string | `sha256hex(output)`. |
| `logs` | string[] *(optional)* | Free-form execution logs. |
| `attestations` | object[] *(optional)* | Verifier-specific attestations (e.g. the signed transcript for `transcript`). |
| `producedAt` | number | Unix epoch ms. |

### 1.3 DeliveryReceipt

The signed settlement outcome. Anyone with the settlement authority's public key can verify it.

| Field | Type | Description |
|-------|------|-------------|
| `protocolVersion` | string | Protocol/canonicalization version. |
| `contractId` | string | The contract this receipt settles. |
| `contractHash` | hex string | `sha256hex(contract)` over the full canonical contract terms. |
| `railId` | string | Settlement rail used for the hold. |
| `holdId` | string | Rail hold this receipt settles. |
| `amount` | number | Held amount this receipt settles (positive, finite). |
| `currency` | string | Currency/asset code this receipt settles. |
| `verdict` | Verdict | The verification result (see §3). |
| `evidenceHash` | hex string | `sha256hex(evidence)` over the full canonical evidence. |
| `routeDecision` | object \| null | Optional verifier-router decision. Present when `routeVerifier` selected the verifier; signed into the receipt so verifier downgrades are tamper-evident. |
| `decision` | `'release' \| 'refund'` | `release` ⇒ pay seller; `refund` ⇒ return buyer funds. |
| `lifecycle` | object[] | Signed lifecycle trace through validation, authorization, verification, receipt signing, and terminal decision preparation. |
| `nonceRegistryKey` | string \| null | Replay-registry key when nonce protection is enabled; signed into the receipt. |
| `signerKeyId` | string | `keyId` of the settlement authority public key. |
| `signature` | base64 string | Ed25519 signature over `canonicalize(receipt-without-signature)`. |
| `issuedAt` | number | Unix epoch ms. |

**Receipt signing & verification.** The signature covers the canonical encoding of the receipt with the `signature` field omitted. `verifyReceipt(receipt, settlementPublicKeyPem)` recomputes that encoding and verifies the Ed25519 signature; it returns `false` if any signed field was tampered. Rotation-aware integrations may also pass `verifyReceipt(receipt, { keys })` or `verifyReceipt(receipt, { keyring })` for verify-only public-key lookup.

---

## 2. Verifiers (predicates)

A `Verifier` consumes a `(contract, evidence)` pair and returns a `Verdict` or `Promise<Verdict>`. Each declares a **tier** (§5). The `predicate.kind` on the contract selects the verifier via the registry:

```js
import { verifiers, getVerifier } from './src/verifiers/index.mjs';
const v = getVerifier(contract.predicate.kind); // throws on unknown
```

The reference build ships eight verifier kinds: seven runnable verifiers and one composition wrapper. Most are Tier A; `signed-oracle` is a runnable Tier B provenance verifier. Interface descriptors for TEE, zkTLS, and ZK proofs are provided but deliberately marked `implemented:false`.

### 2.1 `schemaVerifier` — `kind: 'schema'`  *(the shallow foil)*

Validates `evidence.output` against `predicate.params.schema`. The schema is a small recursive shape:

```
{ type: 'object'|'array'|'number'|'string'|'boolean',
  properties?: { <key>: <schema> },   // for type 'object'
  items?: <schema>,                    // for type 'array'
  required?: string[] }                // for type 'object'
```

`ok = true` iff the output structurally matches (recursive type check, required keys present, array items conform).

This is deliberately kept as the **shallow foil**: HTTP 2xx + JSON-schema shape is exactly what shipped escrow products check, and **schema-valid is not correctness**. A wrong-but-well-formed array passes `schema` and fails `testsuite` (§2.3); a corrupt-but-well-shaped dataset passes `schema` and fails `dataset` (§2.5); a wrong-but-well-shaped API response passes `schema` and fails `api-response` (§2.6); and a valid Markdown string can pass `schema` while failing `document` (§2.7). See the money-shot demos (`examples/demo-compute.mjs` Scenario 4, `examples/demo-dataset.mjs`, `examples/demo-api.mjs`, `examples/demo-document.mjs`).

### 2.2 `hashVerifier` — `kind: 'hash'`

`ok = (sha256hex(evidence.output) === predicate.params.expectedHash)`. Exact-bytes (canonical) match. Use when the buyer already knows the hash of the correct deliverable.

### 2.3 `testsuiteVerifier` — `kind: 'testsuite'`  *(deep Tier A)*

**Objective replay.** `predicate.params = { op: 'sort'|'sum'|'unique'|'reverse', input: any }`. The verifier *recomputes* the expected result from `op` + `input` and deep-equals it against `evidence.output`. Because the verifier reproduces the computation itself, a passing verdict requires **no trust in the seller** — only in the predicate.

The replay runs in a `worker_threads` worker with wall-clock timeout, V8
`resourceLimits`, and preflight input size/depth limits. This bounds deterministic
built-in replay against resource-exhaustion mistakes. It is **not** an OS sandbox
for arbitrary hostile seller code: the worker executes only built-in operations, and
Node's worker limits do not prevent all process-level out-of-memory failures.

### 2.4 `transcriptVerifier` — `kind: 'transcript'`

Nonce-bound signed transcript. `evidence.attestations[0] = { signerKeyId, publicKey (PEM), signature (base64) }`, signed over `canonicalize({ contractId, nonce, outputHash })`.

`ok` iff **all** hold:
- the signature verifies under the attestation's `publicKey`, and
- the signed statement's bound `nonce` equals `contract.nonce`, and
- `outputHash === sha256hex(evidence.output)`, and
- the signer is `contract.seller` or appears in `predicate.params.allowedSignerKeyIds`.

This proves an authorized holder of a key committed to *this* output for *this* contract+nonce (replay-resistant). It does **not** prove the output is *correct* — only that it was attested by the contracted seller or an explicitly allowed attester.

### 2.5 `datasetVerifier` — `kind: 'dataset'`  *(deep tabular correctness)*

Gates settlement on **objective dataset correctness** — content, not just shape — which no shipped settlement rail checks. The deliverable is either an array-of-objects (`json`, the primary path) or an RFC-4180 CSV string (`csv`). `predicate.params` is a `DatasetSpec`:

```jsonc
{
  "format": "json",                 // or "csv" (inferred when omitted: string=>csv, array=>json)
  "columns": [
    { "name": "id",      "type": "number",  "required": true, "nullable": false, "range": { "min": 1 } },
    { "name": "region",  "type": "string",  "required": true, "nullable": false, "domain": ["us","eu","apac"], "regex": "^(us|eu|apac)$" },
    { "name": "revenue", "type": "number",  "required": true, "nullable": false, "range": { "min": 0 }, "maxNullRate": 0 }
  ],
  "rowCount": { "min": 1000, "max": 1000 },
  "merkleRoot": "<sha256 byte-tagged Merkle root>",
  "uniqueKeys": [["id"]],
  "sample":   { "k": 12, "sampleDigest": "<sha256hex>" },
  "aggregates": [
    { "column": "revenue", "op": "sum", "expected": 124500, "tolerance": 0 },
    { "column": "revenue", "op": "avg", "expected": 124.5, "tolerance": 0.01 },
    { "column": "id", "op": "count", "expected": 1000 }
  ]
}
```

The verifier runs six checks **in order** and returns a failing verdict on the **first** broken check, each with a precise `reason` and, for data failures, a structured `diff` shaped like `{ field, expected, actual, row, reason }`:

1. **(i) columns + parseability** — every declared required column is present in every row; the deliverable parses. `required` defaults to `true`; `required:false` allows a missing column value for that row. The CSV parser is a bounded, single-pass RFC-4180 state machine supporting quoted fields, embedded commas/newlines, and escaped `""` quotes. It fails closed on malformed quoting (unterminated quoted field, quote inside an unquoted field, or non-comma text after a closing quote) and enforces document, cell, column, and row caps while parsing.
2. **(ii) row count + optional datasetHash / merkleRoot** — `rowCount.min ≤ rows.length ≤ rowCount.max`. If `predicate.params.datasetHash` or `evidence.datasetHash` is present, it must equal `sha256hex(parsedRows)`. If `predicate.params.merkleRoot` is present, `rowCount.max` must be a non-negative integer bound and the verifier recomputes the byte-tagged Merkle root over the full parsed row set.
3. **(iii) per-field conformance** — `nullable` defaults to `false`. For each non-null cell: `type`, optional `domain` (allowed value set), optional numeric `range`, optional bounded string `regex`, and a per-column `maxNullRate` over the whole column. Regex constraints use JavaScript RegExp source strings but are restricted to a conservative built-in subset: short source strings, bounded input length, and rejection of backreferences, lookaround, nested quantified groups, and quantified alternation groups. This is a verifier DoS guardrail, not a formal safe-regex proof.
4. **(iv) unique keys** — each declared `uniqueKeys` entry (`["id"]` or `["tenantId","email"]`) must be non-null and globally unique across rows.
5. **(v) sample digest** — compute `datasetHash = sha256hex(parsedRows)`, derive `seed = sha256utf8(contract.nonce + "|" + datasetHash)`, select `k` rows by sorting indices on `sha256utf8(seed + ":" + i)`, then check `sha256hex(selectedRowsInSelectionOrder) === sample.sampleDigest`. The seed is verifier-derived from immutable transaction facts, not seller-chosen.
6. **(vi) aggregate invariants** — each `{ column, op, expected, tolerance? }` with `op ∈ {sum, distinct, min, max, avg, count}` must satisfy `|actual − expected| ≤ tolerance` (default `0`).

When `merkleRoot` and `sample` are both present, a passing verdict includes
`verdict.merkle = { root, leafCount, proofs }`, where each proof is shaped
`{ root, leaf, index, leafCount, siblings:[{ side, hash }] }` for one
verifier-seeded sampled row. Leaves are sorted by `canonicalize(row)`, with
duplicate rows retained as distinct leaves at distinct sorted indices. The root
construction is byte-tagged:

```
leaf  = SHA256(0x00 || canonicalize(row))
node  = SHA256(0x01 || leftHashBytes || rightHashBytes)
empty = SHA256(0x02)
```

Odd unpaired nodes are carried up unchanged rather than duplicated. The emitted
proofs let a downstream or on-chain consumer verify that a sampled row is included
in the committed full-row-set root without holding the full dataset.

Honest scope: v0.6 introduced and v0.7 preserves **full-root mode**. The dataset verifier still
receives the full dataset and uses Merkle roots for anti-equivocation plus portable
sample inclusion proofs. Merkle inclusion proves a row is in the committed set; it
does **not** by itself prove global row count, uniqueness, or aggregate truth. Those
properties remain full-set checks.

v0.8 adds explicit **partial Merkle sample mode** as a separate
`dataset-merkle-sample` verifier. The verifier receives only
`evidence.merkleSamples = [{ index, row, proof }]`, not the full dataset. The
contract commits `predicate.params = { merkleRoot, rowCount, k, columns }`.
Sample indices are derived deterministically from
`sha256("deliveryproof.dataset.merkle.sample.v1|nonce|root|rowCount|k")` using
bounded rejection sampling, then sorted ascending in sorted-leaf index space. The
evidence must cover exactly those selected indices: missing, extra, duplicate, or
out-of-range indices fail closed.

For each sample, `proof.root` must equal the committed `merkleRoot`,
`proof.leafCount` must equal the committed `rowCount`, and `proof.index` must equal
the verifier-selected index. The verifier recomputes
`merkleLeafHash(sample.row)` and requires it to match `merkleLeafHash(proof.leaf)`
before checking the Merkle proof; this prevents proving inclusion of one row while
checking a different row. It then applies row-level column constraints only:
`required`, `nullable`, `type`, `domain`, numeric `range`, and bounded `regex`.
Global constraints such as `uniqueKeys`, `aggregates`, `datasetHash`, `sample`,
`sampleDigest`, and full CSV/JSON `format` are rejected in this partial mode.

The partial verdict scope is intentionally narrow: inclusion plus sampled-row
conformance only, **not** full-dataset truth. Use full-root `dataset` mode when the
verifier must prove row count, uniqueness, aggregates, dataset hash, or whole-table
truth.

Every check is a pure function of `(contract, evidence)` and reuses the protocol's `canonicalize`/`sha256hex`, so buyer and verifier always agree on the bytes (Tier A: no third party, no network, no oracle, no LLM). As with all predicates, the contract author still owns whether the spec captures intent.

The correctness taxonomy in the Tier-A core is therefore four complementary deep verifiers: **re-execution** (`testsuite`, §2.3) recomputes the exact answer; **structural/statistical conformance** (`dataset`, §2.5) proves tabular content matches a committed spec and can emit Merkle inclusion proofs for sampled rows; **captured API/MCP response conformance** (`api-response`, §2.6) proves a paid response satisfies a deterministic request/response predicate; and **structured-document conformance** (`document`, §2.7) proves Markdown structure/checksums. Sampling with crypto-attestation (zkML / TEE / zkTLS) remains a Tier-B extension point (§8) and is not in the core.

### 2.6 `apiResponseVerifier` — `kind: 'api-response'`  *(deep API/MCP response correctness)*

Gates settlement on a captured paid API or MCP tool-call transcript. It makes no live network calls; it checks the transcript the seller produced. `evidence.output` must be shaped as:

```jsonc
{
  "contractId": "<must equal contract.id>",
  "nonce": "<must equal contract.nonce>",
  "request":  { "method": "GET", "url": "https://api.example.com/...", "query": {}, "bodyHash": "..." },
  "response": { "status": 200, "headers": { "Content-Type": "application/json" }, "body": {} },
  "producedAt": 1780000000000
}
```

The `contractId` and `nonce` checks are mandatory and run before predicate checks, so a response captured for another contract cannot be replayed into this settlement. `request` is also mandatory: response correctness is defined relative to the request it answers.

`predicate.params` may contain:

```jsonc
{
  "request": { "method": "GET", "url": "https://api.example.com/weather?city=Amsterdam", "bodyHash": "..." },
  "status": { "min": 200, "max": 299 },
  "contentType": "application/json",
  "requiredHeaders": ["Content-Type"],
  "bodySchema": { "type": "object", "required": ["city"] },
  "fields": [
    { "path": "city", "equals": "Amsterdam" },
    { "path": "temperature", "type": "number", "min": -90, "max": 60 },
    { "path": "echo.city", "fromRequest": "query.city" }
  ],
  "freshnessMs": 60000
}
```

Field assertions use a restricted JSON-path resolver (`foo.bar[0]`, no `eval`) and support `equals`, `in`, `min`, `max`, `matches`, `type`, and `fromRequest`. A failing verdict includes a structured first-failure diff such as `{ field, expected, actual, reason }`.

Honest scope: `api-response` proves the response satisfies the declared predicate over the captured transcript bytes. It does **not** prove the external-world fact is true, nor that the bytes genuinely came from the named API. zkTLS/TLSNotary, signed sources, or TEE attestations are Tier-B provenance inputs that can compose with this verifier.

### 2.7 `documentVerifier` — `kind: 'document'`  *(deep structured-document correctness)*

Gates settlement on objective Markdown structure, not prose quality. `evidence.output` must be a Markdown string. The verifier normalizes line endings and can check:

- optional `documentHash = sha256utf8(normalizedMarkdown)`;
- YAML-like frontmatter required keys and simple scalar field checks;
- required headings by text/level/count;
- required terms by exact substring count;
- link schemes and required hrefs;
- Markdown table headers;
- fenced code-block languages/counts;
- document or section checksums.

Before hashing or parsing, the verifier enforces fixed resource bounds: maximum
document length, maximum line length, and maximum line count. These bounds make the
fixed Markdown parser regexes practical CWE-400 guardrails; they are not an
arbitrary-Markdown security sandbox.

This verifier is Tier A because every check is a pure function of `(contract, evidence)`. It does **not** grade whether the document is well-written, true, sufficient, or useful.

### 2.8 `composeVerifier` — `kind: 'compose'`

Combines child verifier predicates without changing the settlement engine. The
contract predicate is shaped as:

```jsonc
{
  "kind": "compose",
  "params": {
    "mode": "all",                 // "all" | "any" | "threshold"
    "threshold": 2,                // required only for threshold mode
    "verifiers": [
      { "kind": "api-response", "params": {} },
      { "kind": "signed-oracle", "params": {} }
    ]
  }
}
```

`all` passes only when all children pass; `any` passes when at least one child
passes; `threshold` passes when at least `threshold` children pass. The verifier
records a child trace with each child verdict and signs that trace into the final
receipt as part of the `verdict`. Nested `compose` is intentionally rejected in the
core. The router treats an explicit `compose` predicate as non-bypassable:
it may not silently satisfy a composed contract with `schema` or `hash`.

### 2.9 `signedOracleVerifier` — `kind: 'signed-oracle'`  *(Tier B provenance)*

Verifies a real Ed25519 oracle/provenance attestation over a canonical statement:

```jsonc
{
  "contractId": "<contract.id>",
  "nonce": "<contract.nonce>",
  "outputHash": "<sha256hex(evidence.output)>",
  "source": "weather-api.example",
  "claimType": "api-response-provenance",
  "producedAt": 1780000000000
}
```

`ok` iff the signature verifies, the signer key derives to an allowed attester key
id, and all bound fields match the current contract and output. Optional predicate
params constrain `source`, `claimType`, and maximum age. This proves only that an
authorized attester said the statement; it does not prove the external-world fact is
true. TEE, zkTLS, and ZK proof variants share the same provenance-binding shape but
are shipped as explicit interface descriptors, not fake cryptography.

Every `verify()` returns a full `Verdict` with a clear `reason` on both success and failure.

---

## 3. Verdict

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | Did the deliverable satisfy the predicate? |
| `tier` | `'A' \| 'B' \| 'C'` | Trust tier of the verifier that produced this. |
| `verifier` | string | Verifier name. |
| `reason` | string | Human-readable explanation (always set, pass or fail). |
| `diff` | object *(optional)* | Structured first-failure diff for data verifiers: `{ field, expected, actual, row, reason }`. |
| `trace` | object[] *(optional)* | Child-verifier trace for composed predicates. |
| `provenance` | object *(optional)* | Attestation/proof metadata for Tier-B verifiers. |
| `merkle` | object *(optional)* | Dataset Merkle proof bundle: `{ root, leafCount, proofs:[{ root, leaf, index, leafCount, siblings }] }`. Present only on passing dataset verdicts with both `merkleRoot` and `sample`. |
| `checkedAt` | number | Unix epoch ms. |

---

## 4. Interfaces

### 4.1 Verifier

```
Verifier {
  name: string
  tier: 'A' | 'B' | 'C'
  verify(contract: DeliveryContract, evidence: DeliveryEvidence): Verdict | Promise<Verdict>
}
```

`verify` must be pure with respect to its inputs and must not move money. It only *judges*.

### 4.2 Verifier router

`routeVerifier(contract, { policy, registry?, profiles? })` chooses the cheapest verifier that is still sufficient for a declared risk policy.

```
VerifierPolicy {
  deliverableType?: string   // 'dataset' | 'compute' | 'any' (default)
  minAssurance: number       // 1 shape, 2 integrity, 3 deep correctness
  fallbackAllowed?: boolean  // default false: throw instead of silently downgrading
  maxCost?: number
}
```

Built-in assurance levels are static and non-gameable:

| Verifier | Assurance | Cost | Applies to |
|----------|-----------|------|------------|
| `schema` | 1 shape | 1 | `*` |
| `hash` | 2 integrity | 2 | `*` |
| `transcript` | 2 integrity | 3 | `*` |
| `testsuite` | 3 deep correctness | 4 | `compute` |
| `dataset` | 3 deep correctness | 5 | `dataset` |
| `api-response` | 3 deep correctness | 4 | `api-response` |
| `document` | 3 deep correctness | 4 | `document` |
| `compose` | derived from children | derived | `*` (explicit compose only) |
| `signed-oracle` | 2 provenance | 3 | `provenance`, `api-response`, `*` (explicit signed-oracle only) |

If no verifier meets `minAssurance`, the router throws unless `fallbackAllowed:true`; any fallback is flagged as `fallbackUsed:true` in `routeDecision`. The engine signs `routeDecision` into the receipt, so a buyer can later prove which verifier was selected and whether a downgrade happened.

Explicit `compose` and `signed-oracle` predicates are non-bypassable: when a
contract names one of those verifier kinds, the router considers that kind only
rather than a cheaper lower-assurance profile that happens to fit the deliverable
type.

### 4.3 RailAdapter

```
RailAdapter {
  id: string
  authorize(contract: DeliveryContract): Hold | Promise<Hold>
  capture(hold: Hold, receipt: DeliveryReceipt): Hold | Promise<Hold>
  refund(hold: Hold, receipt: DeliveryReceipt): Hold | Promise<Hold>
  status(holdId: string): Hold | Promise<Hold>
  flush?(): void | Promise<void>
  close?(): void | Promise<void>
  health?(): object | Promise<object>
}
```

`flush`, `close`, and `health` are optional operability helpers for local adapters.
They are not required for protocol conformance and do not imply a hosted service.

### 4.4 Hold

| Field | Type | Description |
|-------|------|-------------|
| `holdId` | string | Unique hold id. |
| `contractId` | string | The contract this hold backs. |
| `amount` | number | Held amount (= `contract.price.amount`). |
| `currency` | string | Currency code. |
| `state` | `'held' \| 'captured' \| 'refunded'` | Current state. |
| `history` | object[] | Append-only transitions: `{ state, at, receiptRef? }`. |

---

## 5. Verifier tiers (trust model)

DeliveryProof makes trust **explicit and tiered**. The tier on a `Verdict` tells the buyer what residual trust a *passing* verdict still requires.

| Tier | Name | What a pass means | Residual trust |
|------|------|-------------------|----------------|
| **A** | Objective | Independently recomputable or cryptographically self-evident. | Only the predicate. |
| **B** | Attested | Backed by an external proof system (ZK / TEE / zkTLS / signed oracle). | The soundness of that system/hardware/source. |
| **C** | Subjective | A model or rubric judged quality. Advisory signal. | The judge. |

Most shipped verifiers are **Tier A**. `signed-oracle` is the runnable Tier-B
example; TEE, zkTLS, and ZK are interface descriptors only (§8). Tier C remains an
extension point.

### The four irreducible trust points

Tiering organizes — but does not eliminate — these:

1. **Predicate authorship.** The buyer trusts the predicate captures intent.
2. **External-truth sources.** zkTLS/oracles prove *"the source said X"*, not *"X is true"*.
3. **Subjective/semantic quality.** Not objectively verifiable in general.
4. **Settlement-rail policy.** The rail defines what capture/refund actually mean.

DeliveryProof's job is to name and scope these, not to claim they're gone.

---

## 6. Canonicalization & hashing

- `canonicalize(obj)` produces deterministic RFC-8785-style JCS JSON: object keys are recursively sorted, array order is preserved, non-I-JSON values are rejected, and no whitespace is emitted. Two objects that differ only in key insertion order canonicalize identically.
- `sha256hex(input)` is the protocol commitment hash: lowercase SHA-256 over `canonicalize(input)`.
- `sha256utf8(text)` and `sha256bytes(bytes)` are explicit raw-domain helpers for non-protocol text/byte hashing.
- `PROTOCOL_VERSION` currently equals `deliveryproof/0.4-jcs1`; core wire objects must carry it.

These guarantee that hashes and signatures are stable across encoders and machines.

---

## 7. Settlement state machine

A hold is created on `authorize` and moves **once** to a terminal state.

```
                 authorize(contract)
                        │
                        ▼
                   ┌─────────┐
                   │  held   │
                   └─────────┘
                    │       │
   decision=release │       │ decision=refund
   capture(hold,r)  │       │ refund(hold,r)
                    ▼       ▼
            ┌──────────┐ ┌───────────┐
            │ captured │ │ refunded  │   (terminal)
            └──────────┘ └───────────┘
```

Transition rules (enforced by the rail):

- **`authorize(contract)`** → creates `Hold { state: 'held', amount = contract.price.amount, currency, history: [{ state:'held', at }] }`.
- **`capture(hold, receipt)`** → **requires** `receipt.decision === 'release'` **and** current state `'held'`. Sets `'captured'`; appends history with `receiptRef = receipt.signature.slice(0, 16)`. *(Seller paid.)*
- **`refund(hold, receipt)`** → **requires** `receipt.decision === 'refund'` **and** current state `'held'`. Sets `'refunded'`; appends history. *(Buyer refunded.)*
- **`status(holdId)`** → returns the current `Hold`.

The mock rail logs each transition, e.g. `[escrow] hold abc123 held->captured (amount 5 USDC)`.

### Engine orchestration (`settle`)

```
settle({ contract, produceEvidence, verifier, rail, settlementKey,
         routeDecision?, nonceRegistry?, now?, auditSink? }):
  0. normalizedContract = { protocolVersion, ...contract }
     optional nonceRegistry.reserve(...) before authorize
  1. hold     = await rail.authorize(normalizedContract)
  2. evidence = await produceEvidence(normalizedContract, { signal })
               // engine ensures evidence.outputHash = sha256hex(evidence.output),
               //                  evidence.nonce     = contract.nonce,
               //                  evidence.contractId = contract.id
  3. verdict  = await verifier.verify(normalizedContract, evidence)
               // producer/verifier exceptions after authorize become ok=false
               // verdicts so the held funds can be refunded instead of stranded
  4. decision = verdict.ok ? 'release' : 'refund'
  5. receipt  = sign settlement authority over
                canonicalize(receipt-without-signature)
               // includes routeDecision, lifecycle, nonceRegistryKey
  6. if release: await rail.capture(hold, receipt)
     else:       await rail.refund(hold, receipt)
     optional nonceRegistry.mark(...)
  7. return { contract, evidence, verdict, receipt, hold }
```

**Gating invariant (normative).** There is **no path** in which a hold is `captured` while `verdict.ok === false`. A failing verdict can only lead to `refund`. The engine test suite asserts this directly.

**Audit hooks.** `auditSink` is optional and best-effort. Audit events are emitted
at engine/router/rail boundaries for observability, but audit sink failures are
ignored and audit fields are never signed into `DeliveryReceipt`. Audit therefore
cannot change settlement decisions or receipt bytes.

**SLA/deadline.** If `contract.sla.deadlineMs` and a positive `createdAt` are
present, delivery must complete before `createdAt + deadlineMs`. Late delivery
throws before or after evidence production and is converted into a refund verdict.
The producer receives an `AbortSignal`, but the engine also checks the deadline
after delivery for producers that ignore the signal.

**Nonce replay registry.** When a `nonceRegistry` is supplied, `settle()` reserves
the nonce before `authorize()`. The key includes protocol version, settlement
authority key id, buyer, seller, rail id, and nonce; it intentionally excludes
`contract.id`, so replaying the same nonce under a new contract id is rejected
before any hold is created. A nonce is burned on **any** settlement attempt,
including refunds and failed verification; retrying requires a fresh nonce.

**Durable local rail.** `src/rails/durable-rail.mjs` implements the same adapter
interface with an append-only JSONL write-ahead log, idempotency keys, fingerprint
conflict checks, terminal-operation idempotency, and recovery across process
restarts. Its scope is exactly-once **local terminalization**. It does not claim
universal exactly-once movement across external payment networks.

### 7.1 Milestone / partial-delivery composition

Partial delivery/refund is modeled as composition over independent child
contracts, not as fractional mutation of one escrow hold. `compileMilestoneContracts`
validates a schedule, checks integer amounts and currency uniformity, and requires
the child prices to sum exactly to `totalPrice.amount`. It then derives unique child
ids/nonces from the parent schedule.

`settleMilestones()` runs each child through the normal `settle()` engine. Therefore
every released milestone has its own signed `DeliveryReceipt` whose decision came
from `verdict.ok`. `verifyMilestoneAggregate(aggregate, settlementPublicKey)`
verifies every child receipt signature and receipt hash, cross-checks signed child
amount/currency/decision against the aggregate entry, and recomputes
released/refunded totals from the signed receipts.

Completeness is an explicit stronger mode, not inferred from attacker-controlled
aggregate fields. `verifyMilestoneAggregate(aggregate, settlementPublicKey, {
schedule })` additionally recomputes the expected child contracts from the schedule
and verifies `scheduleHash`, `childCount`, child order, milestone ids, child
contract ids, and child contract hashes. Use this schedule-bound mode when
truncation, reordering, or substituted child receipts are in scope. The two-argument
mode proves per-child receipt validity and internal accounting consistency, but it
does **not** prove the aggregate contains the complete schedule.

---

## 8. Extension points

The interfaces in §4 are the stable surface. The reference implementations are swappable.

### 8.1 Real settlement rails (`RailAdapter`)

Implement `authorize / capture / refund / status` against a real rail. The engine is rail-neutral; it only needs the four methods and the `Hold` shape.

- **Coinbase x402.** `authorize` ⇒ open/escrow the x402 payment intent for `contract.price`; `capture` ⇒ settle to the seller on `release`; `refund` ⇒ void/return on `refund`; `status` ⇒ query the payment state. Map x402 finality semantics into `held → captured/refunded`.
- **Stripe MPP (agentic payments).** `authorize` ⇒ a manual-capture PaymentIntent (funds authorized, not captured); `capture` ⇒ `paymentIntents.capture`; `refund` ⇒ cancel/refund; `status` ⇒ retrieve. The DeliveryReceipt becomes the off-rail justification for capture.
- **Google AP2 mandates.** Treat the AP2 *mandate* as the authorization. `authorize` validates the mandate covers the contract; `capture`/`refund` execute within the mandate's constraints; the signed receipt is the delivery proof attached to the mandate execution.
- **Card rails (Visa/Mastercard agent programs).** Auth-and-capture maps naturally: `authorize` = authorization hold, `capture` = clearing, `refund` = reversal/refund. Rail policy (chargeback windows, finality) is the trust point named in §5.

A production rail should persist holds durably and make transitions idempotent on
`holdId` + decision. The in-repo `durable-rail` demonstrates a local WAL/idempotency
pattern; the default demo rail remains an in-memory mock for readability.

### 8.2 Higher-tier verifiers (`Verifier`)

Add verifiers that declare `tier: 'B'` or `tier: 'C'`. They implement the same `verify(contract, evidence): Verdict | Promise<Verdict>` contract and register in `verifiers/index.mjs`.

- **Tier B — ZK proof.** `evidence.attestations` carries a proof + public inputs; `verify` checks the proof against a verifying key bound to the predicate. A pass means *the computation was done correctly* under the proof system's soundness.
- **Tier B — TEE attestation.** `evidence.attestations` carries a remote-attestation quote over the enclave measurement and output; `verify` checks the quote chains to a trusted root and matches the expected measurement.
- **Tier B — zkTLS / web-proof.** Proves *"server S returned response R over TLS"*. `verify` checks the zkTLS transcript and binds `R` to `evidence.outputHash` and the contract `nonce`. Names trust point #2: it proves provenance, not ground truth.
- **Tier B — signed oracle.** Implemented in this reference build. `verify` checks a real Ed25519 signature over a canonical statement bound to `contractId`, `nonce`, `outputHash`, source, claim type, and `producedAt`; trust is the oracle's key and honesty.
- **Tier C — LLM-as-judge / rubric.** `verify` scores `evidence.output` against a rubric and thresholds it. Advisory; trust is the judge. Should never be presented as Tier A.

### 8.3 Paid-tool integration

`paidToolWithDeliveryProof({ tool, makeContract, makeEvidence?, verifier, rail, settlementKey })` wraps a seller's tool `async (input) => output` into `async (input) => settle-result`: it builds a contract via `makeContract(input)`, adapts `tool` into a `produceEvidence` function (capturing `output`, computing `outputHash`, binding the `nonce`), optionally lets `makeEvidence({ input, contract, output })` attach verifier-specific logs or attestations, and runs `settle`. This models an MCP paid tool whose **payment releases only on verified delivery**. In production this becomes MCP-SDK middleware around the paid endpoint.

### 8.4 ERC projection helpers

`toErc8004ValidationPayload()` and `toErc8183EvaluatorResult()` project a signed
receipt into standard-shaped validation/evaluator payloads. SHA-256 remains the
default `hashAlg` for backward compatibility. Callers may opt into
`hashAlg: 'keccak256'`, which uses `@noble/hashes` for Ethereum Keccak-256, and
`includeAbi: true`, which attaches ABI-shaped argument bytes.

These helpers are projection only. They do not include selectors, wallet signing,
provider/RPC configuration, private-key handling, contract-call helpers, or
on-chain submission.

---

## 9. Reference implementation map

| Spec section | Module |
|--------------|--------|
| §1 objects (typedefs) | `src/protocol/types.mjs` |
| §6 canonicalization & hashing | `src/protocol/canonical.mjs` |
| Ethereum Keccak-256 helper | `src/protocol/keccak.mjs` |
| dataset Merkle proofs | `src/protocol/merkle.mjs` |
| runtime schema validation | `src/protocol/schema.mjs` |
| runtime validation helpers / errors | `src/runtime.mjs`, `src/errors.mjs` |
| signatures / identity | `src/protocol/crypto.mjs` |
| §2 verifiers | `src/verifiers/{schema,hash,testsuite,transcript,dataset,api-response,document,compose,index}.mjs` |
| Tier-B provenance | `src/verifiers/tier-b/{interfaces,signed-oracle}.mjs` |
| §4.2 verifier router | `src/router/policy.mjs` |
| §4.3 rails | `src/rails/escrow-mock.mjs`, `src/rails/durable-rail.mjs` |
| §7 engine (`settle`, `verifyReceipt`) | `src/engine/deliveryproof.mjs` |
| §7.1 milestone composition | `src/engine/milestones.mjs` |
| operability helpers / audit hooks | `src/operability/index.mjs` |
| §8.3 paid-tool wrapper | `src/mcp/paidToolWithDeliveryProof.mjs` |
| §8.4 ERC projection helpers | `src/interop/{erc8004,erc8183,abi}.mjs` |
| runnable scenarios | `examples/demo-compute.mjs` (compute money shot), `examples/demo-dataset.mjs` (dataset money shot), `examples/demo-api.mjs` (API/MCP response money shot), `examples/demo-document.mjs` (document money shot), `examples/demo-merkle-partial.mjs` (partial Merkle money shot), `examples/demo-interop.mjs` (ERC export), `examples/demo-keyring.mjs` (verification-only key rotation), `examples/demo-audit-bundle.mjs` (dispute/audit bundle), `examples/demo-keccak-interop.mjs` (sha256 vs keccak ERC projection), `examples/demo-production-seams.mjs` (rail/replay-store conformance seams) |
| conformance tests | `test/{protocol,protocol-schema,verifiers,testsuite-sandbox,engine,engine-lifecycle,router,compose,tier-b,mcp,interop,api-response,document,dataset-merkle-sample,milestones,durable-rail,merkle,merkle-sample,keccak,operability,package,production-hardening}.test.mjs` |

---

## 10. License

Apache-2.0
