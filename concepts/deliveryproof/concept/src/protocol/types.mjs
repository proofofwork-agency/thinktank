// types.mjs — protocol type definitions (JSDoc @typedef only).
//
// This module intentionally contains NO runtime logic. It is the single source
// of truth for the shape of every object that crosses a DeliveryProof boundary:
// the three core records (Contract / Evidence / Receipt), the supporting value
// objects (Verdict, Hold), and the two extension interfaces (Verifier,
// RailAdapter). Importing this module costs nothing at runtime; it exists so
// editors and readers share one vocabulary.
//
// The honest frame, restated for implementers: DeliveryProof converts hidden
// trust into explicit, composable, tiered trust. It does not abolish trust.
// Four trust points remain irreducible:
//   (1) predicate authorship  — buyer trusts the predicate captures intent;
//   (2) external-truth sources — zkTLS/oracles prove "source said X", not "X is true";
//   (3) subjective/semantic AI quality — not objectively verifiable in general;
//   (4) settlement-rail policy — the rail decides capture/refund semantics.

// ---------------------------------------------------------------------------
// Core record: DeliveryContract
// ---------------------------------------------------------------------------

/**
 * The predicate that defines what "delivered" means for a contract.
 *
 * @typedef {Object} DeliveryPredicate
 * @property {'schema'|'hash'|'builtin-replay'|'testsuite'|'transcript'|'dataset'|'dataset-merkle-sample'|'api-response'|'document'|'compose'|'signed-oracle'} kind
 *   Which verifier evaluates the deliverable.
 *     - 'schema'     : output must match a declared shape (Tier A, shallow shape-only).
 *     - 'hash'       : output hash must equal an expected hash (Tier A).
 *     - 'builtin-replay'  : reference computation is re-executed and compared (Tier A, deep).
 *     - 'testsuite'       : deprecated alias for 'builtin-replay'.
 *     - 'transcript' : a nonce-bound signed transcript attests delivery (Tier A).
 *     - 'dataset'    : a tabular deliverable is checked for DEEP correctness — column
 *                      presence, row count, required/nullable semantics, per-field
 *                      type/domain/range/regex/null-rate, unique keys, a
 *                      verifier-seeded sample-hash, and aggregate invariants
 *                      (Tier A, deep).
 *     - 'dataset-merkle-sample': partial dataset mode. Verifier-selected sorted
 *                      leaf indices are proven included in a committed Merkle
 *                      root and checked against row-level column constraints only.
 *                      This proves inclusion + sampled-row conformance, NOT
 *                      full-dataset truth.
 *     - 'api-response': a captured paid API/MCP transcript is checked for DEEP
 *                      response correctness — mandatory contractId+nonce binding,
 *                      request binding, status/header/body checks, JSON-path field
 *                      assertions, request/response equality, and freshness (Tier A, deep).
 *     - 'document'   : a Markdown deliverable is checked for objective structure —
 *                      frontmatter, headings, required terms, links, tables,
 *                      code-block languages, and checksums (Tier A, deep).
 *     - 'compose'    : multiple verifiers are combined under all/any/threshold
 *                      predicate algebra with a signed child-verdict trace.
 *     - 'signed-oracle': Tier-B provenance: an allowed attester signed a claim
 *                      over {contractId, nonce, outputHash, source, claim}.
 * @property {Object} params
 *   Verifier-specific parameters. By kind:
 *     - schema:     { schema: ShapeSchema }
 *     - hash:       { expectedHash: string }   // lowercase hex sha256 of output
 *     - builtin-replay:  { op: 'sort'|'sum'|'unique'|'reverse', input: any,
 *                     timeoutMs?: number, maxInputBytes?: number, maxDepth?: number }
 *     - transcript: {}                          // verification data travels in evidence
 *     - dataset:    DatasetSpec                 // see @typedef DatasetSpec below
 *     - dataset-merkle-sample: DatasetMerkleSampleSpec // see typedef below
 *     - api-response: ApiResponseSpec           // see @typedef ApiResponseSpec below
 *     - document:   DocumentSpec                // see @typedef DocumentSpec below
 *     - compose:    { mode: 'all'|'any'|'threshold', threshold?: number,
 *                     verifiers: Array<{ kind: DeliveryPredicate.kind, params: Object }> }
 *     - signed-oracle: { allowedAttesterKeyIds: string[], source?: string,
 *                        claimType?: string, maxAgeMs?: number }
 */

/**
 * Parameters for the dataset verifier (predicate.kind === 'dataset'). Every field
 * is committed in the signed contract, so the verdict is a pure function of the
 * contract and the delivered table (Tier A: no third-party trust).
 *
 * @typedef {Object} DatasetColumn
 * @property {string} name                       Column name that must exist in every row.
 * @property {'string'|'number'|'boolean'} type  Required non-null cell type.
 * @property {boolean} [required]                Defaults true. If false, missing cells are allowed.
 * @property {boolean} [nullable]                Defaults false. If true, null/undefined cells are allowed.
 * @property {Array<*>} [domain]                 Optional allowed value set (membership check).
 * @property {{min?:number,max?:number}} [range] Optional inclusive numeric bounds.
 * @property {string} [regex]                    Optional bounded RegExp source for string cells.
 * @property {number} [maxNullRate]              Optional max fraction of null/missing cells [0,1].
 *
 * @typedef {Object} DatasetSample
 * @property {number} k            How many rows to select.
 * @property {string} sampleDigest Committed sha256hex(verifier-seeded rows).
 *
 * @typedef {Object} DatasetAggregate
 * @property {string} column                       Column the aggregate runs over.
 * @property {'sum'|'distinct'|'min'|'max'|'avg'|'count'} op Aggregate operation.
 * @property {number} expected                     Committed expected result.
 * @property {number} [tolerance]                  Optional absolute tolerance (default 0).
 *
 * @typedef {Object} DatasetSpec
 * @property {'json'|'csv'} [format]        Deliverable format (inferred when omitted:
 *                                          string => csv, array => json).
 * @property {DatasetColumn[]} columns      Declared columns (non-empty).
 * @property {{min?:number,max?:number}} rowCount Allowed row-count window.
 * @property {string} [datasetHash]         Optional full parsed-row commitment.
 * @property {string} [merkleRoot]          Optional full-row-set Merkle root commitment.
 * @property {(string|string[])[]} [uniqueKeys] Optional unique key constraints.
 * @property {DatasetSample} [sample]       Optional verifier-seeded sample-hash commitment.
 * @property {DatasetAggregate[]} [aggregates] Optional aggregate invariants.
 */

/**
 * Parameters for the partial Merkle dataset verifier
 * (predicate.kind === 'dataset-merkle-sample'). Unlike DatasetSpec, this mode
 * does not receive or scan the full dataset. It proves only that the supplied
 * sampled rows are included in the committed root and satisfy row-level column
 * constraints. Global constraints such as uniqueKeys, aggregates, datasetHash,
 * sampleDigest, and full rowCount truth require the full dataset verifier.
 *
 * @typedef {Object} DatasetMerkleSampleSpec
 * @property {string} merkleRoot          Lowercase 64-hex SHA-256 Merkle root
 *                                       committed over sorted dataset leaves.
 * @property {number} rowCount            Authoritative committed leaf count.
 * @property {number} k                   Verifier-selected sample size. If
 *                                       rowCount < k, every row index is required.
 * @property {DatasetColumn[]} columns    Row-level constraints applied only to
 *                                       supplied sampled rows. Supported column
 *                                       checks: required, nullable, type, domain,
 *                                       range, and bounded regex.
 *
 * @typedef {Object} DatasetMerkleProofSibling
 * @property {'left'|'right'} side
 * @property {string} hash Lowercase 64-hex sibling hash.
 *
 * @typedef {Object} DatasetMerkleSampleProof
 * @property {string} root
 * @property {*} leaf
 * @property {number} index Sorted-leaf index.
 * @property {number} leafCount
 * @property {DatasetMerkleProofSibling[]} siblings
 *
 * @typedef {Object} DatasetMerkleSampleItem
 * @property {number} index Sorted-leaf index selected by the verifier.
 * @property {Object} row Row content whose tagged Merkle leaf hash must equal
 *                       proof.leaf's tagged Merkle leaf hash.
 * @property {DatasetMerkleSampleProof} proof
 *
 * @typedef {Object} DatasetMerkleSampleEvidence
 * @property {DatasetMerkleSampleItem[]} merkleSamples Partial Merkle samples
 *                                                     covering exactly the
 *                                                     verifier-selected indices.
 */

/**
 * Parameters for the API/MCP response verifier (predicate.kind === 'api-response').
 * The verifier checks a captured transcript in evidence.output and does not make
 * live network calls. The transcript must include contractId, nonce, request,
 * response, and optionally producedAt.
 *
 * @typedef {Object} ApiResponseFieldAssertion
 * @property {string} path                         Restricted JSON path into response.body.
 * @property {*} [equals]                          Expected exact canonical value.
 * @property {Array<*>} [in]                       Allowed canonical values.
 * @property {number} [min]                        Inclusive numeric lower bound.
 * @property {number} [max]                        Inclusive numeric upper bound.
 * @property {string} [matches]                    JavaScript RegExp source for string values.
 * @property {'string'|'number'|'boolean'|'object'|'array'} [type] Required value type.
 * @property {string} [fromRequest]                Restricted JSON path into request; response
 *                                                value must equal that request value.
 *
 * @typedef {Object} ApiResponseSpec
 * @property {{method?:string,url?:string,bodyHash?:string}} [request] Expected request binding.
 * @property {number|{min?:number,max?:number}} [status] Expected response status or range.
 * @property {string} [contentType]                Exact response content-type header.
 * @property {string[]} [requiredHeaders]          Header names that must be present.
 * @property {ShapeSchema} [bodySchema]            Optional structural floor for response.body.
 * @property {ApiResponseFieldAssertion[]} [fields] Deterministic response-body assertions.
 * @property {number} [freshnessMs]                producedAt must be within this many ms of contract.createdAt.
 */

/**
 * Parameters for the document verifier (predicate.kind === 'document'). The
 * verifier is strictly objective: it checks Markdown bytes and structure, not
 * prose quality or semantic truth.
 *
 * @typedef {Object} DocumentSpec
 * @property {'markdown'} [format]                 Only Markdown is implemented.
 * @property {string} [documentHash]               Optional sha256utf8(normalized markdown).
 * @property {{required?:string[],fields?:Object}} [frontmatter] Frontmatter shape checks.
 * @property {Array<{text:string,level?:number,minCount?:number,maxCount?:number,caseSensitive?:boolean}>} [headings]
 * @property {Array<string|{text:string,minCount?:number,caseSensitive?:boolean}>} [requiredTerms]
 * @property {{allowedSchemes?:string[],required?:string[]}} [links]
 * @property {Array<{headers:string[],mode?:'exact'|'contains'}>} [tables]
 * @property {Array<{language?:string,minCount?:number,maxCount?:number}>} [codeBlocks]
 * @property {Array<{target?:'document'|'section',heading?:string,level?:number,caseSensitive?:boolean,sha256:string}>} [checksums]
 */

/**
 * The price of a deliverable.
 *
 * @typedef {Object} Price
 * @property {number} amount   Numeric amount (rail-neutral; e.g. token/minor units).
 * @property {string} currency Currency or asset code (e.g. "USDC").
 */

/**
 * Service-level terms.
 *
 * @typedef {Object} Sla
 * @property {number} deadlineMs Allowed delivery window in milliseconds.
 */

/**
 * A signed-intent agreement between buyer and seller that binds a payment to an
 * explicit, machine-checkable delivery predicate. This is the object that turns
 * "the agent was allowed to pay" into "and the counterparty must deliver X".
 *
 * @typedef {Object} DeliveryContract
 * @property {string} protocolVersion  DeliveryProof wire protocol version.
 * @property {string} id               Unique contract id.
 * @property {string} buyer            Buyer key id (see crypto.keyId).
 * @property {string} seller           Seller key id (see crypto.keyId).
 * @property {string} intent           Human-readable statement of what is bought.
 * @property {string} deliverableType  Type tag of the deliverable (e.g. "array", "json", "document").
 * @property {DeliveryPredicate} predicate The verifiable delivery condition.
 * @property {Price} price             What the buyer pays on verified delivery.
 * @property {Sla} sla                 Service-level terms (deadline).
 * @property {string} refundRule       Human-readable refund policy description.
 * @property {string} railId           Id of the settlement rail adapter to use.
 * @property {string} nonce            Unique per-contract nonce; binds evidence/transcripts.
 * @property {number} createdAt        Creation timestamp (ms since epoch).
 */

// ---------------------------------------------------------------------------
// Core record: DeliveryEvidence
// ---------------------------------------------------------------------------

/**
 * The seller's produced deliverable plus everything needed to verify it.
 *
 * @typedef {Object} DeliveryEvidence
 * @property {string} protocolVersion DeliveryProof wire protocol version.
 * @property {string} contractId     Id of the contract this evidence fulfills.
 * @property {string} nonce          Must equal contract.nonce (replay/binding guard).
 * @property {*} output              The actual deliverable.
 * @property {string} outputHash     lowercase hex sha256 of `output` (canonical).
 * @property {string} [datasetHash]  Optional lowercase hex sha256 of canonical parsed rows
 *                                   for dataset deliverables.
 * @property {string} [documentHash] Optional lowercase hex sha256utf8(normalized markdown)
 *                                   for document deliverables.
 * @property {string[]} [logs]       Optional execution/diagnostic logs.
 * @property {Object[]} [attestations]
 *   Optional attestations. For the transcript verifier, attestations[0] is:
 *     { signerKeyId: string, publicKey: string (PEM),
 *       signature: string (b64) over canonical({contractId, nonce, outputHash}) }.
 * @property {number} producedAt     Production timestamp (ms since epoch).
 */

// ---------------------------------------------------------------------------
// Value object: Verdict
// ---------------------------------------------------------------------------

/**
 * The result of verifying evidence against a contract's predicate.
 *
 * Tiers encode HOW MUCH external trust the verdict required:
 *   - 'A' : objective, no third-party trust (recompute/hash/schema/signed-transcript).
 *   - 'B' : trust-minimized via cryptographic external proofs (ZK / TEE / zkTLS).
 *           "Source said X", proven; not "X is true".
 *   - 'C' : subjective / semantic judgment (e.g. LLM quality grading). Lowest
 *           assurance; inherently not objectively verifiable in general.
 *
 * @typedef {Object} Verdict
 * @property {boolean} ok        Whether the deliverable satisfies the predicate.
 * @property {'A'|'B'|'C'} tier  Trust tier of this verification.
 * @property {string} verifier   Name of the verifier that produced this verdict.
 * @property {string} reason     Human-readable explanation (on both pass and fail).
 * @property {Object} [diff]     Optional structured first-failure diff for data verifiers:
 *                               { field, expected, actual, row, reason }.
 * @property {Object[]} [trace]  Optional verifier-composition trace, signed into receipts
 *                               when present.
 * @property {Object} [provenance] Optional Tier-B provenance summary.
 * @property {Object} [merkle]   Optional dataset Merkle proof bundle for sampled rows:
 *                               { root, leafCount, proofs:[{ root, leaf, index, leafCount, siblings }] }.
 * @property {Object} [merkleSample] Optional partial dataset Merkle result:
 *                               { root, rowCount, k, indices, samples:[{ index, row, leafHash }] }.
 * @property {number} checkedAt  Verification timestamp (ms since epoch).
 */

// ---------------------------------------------------------------------------
// Core record: DeliveryReceipt
// ---------------------------------------------------------------------------

/**
 * A signed, portable record of the settlement decision. Verifiable by anyone
 * holding the settlement authority's public key.
 *
 * @typedef {Object} DeliveryReceipt
 * @property {string} protocolVersion DeliveryProof wire protocol version.
 * @property {string} contractId  Id of the settled contract.
 * @property {string} contractHash lowercase hex sha256 of the canonical contract.
 * @property {string} railId      Id of the rail used to authorize/capture/refund.
 * @property {string} holdId      Rail hold id this receipt settles.
 * @property {number} amount      Held amount this receipt settles.
 * @property {string} currency    Currency/asset code this receipt settles.
 * @property {Verdict} verdict     The verdict that drove the decision.
 * @property {string} evidenceHash lowercase hex sha256 of the canonical evidence.
 * @property {Object|null} routeDecision Optional verifier-router decision, signed into
 *                                       the receipt when routing was used.
 * @property {Object[]} lifecycle Ordered settlement lifecycle events, signed into
 *                                the receipt for deadline/replay auditability.
 * @property {string|null} nonceRegistryKey Optional replay-registry key when a
 *                                          registry was used.
 * @property {'release'|'refund'} decision Settlement action taken.
 * @property {string} signerKeyId  Key id of the settlement authority.
 * @property {string} signature    base64 Ed25519 signature over the canonical
 *                                 receipt WITHOUT its `signature` field.
 * @property {number} issuedAt     Issuance timestamp (ms since epoch).
 */

// ---------------------------------------------------------------------------
// Value object: Hold (rail settlement state)
// ---------------------------------------------------------------------------

/**
 * One entry in a Hold's state-transition history.
 *
 * @typedef {Object} HoldHistoryEntry
 * @property {'held'|'captured'|'refunded'} state Resulting state after the transition.
 * @property {number} at            Transition timestamp (ms since epoch).
 * @property {string} [receiptRef]  Short reference to the receipt that caused it.
 */

/**
 * The settlement-rail's view of funds for a contract. State machine:
 *   held -> captured   (seller paid; only when verdict.ok)
 *   held -> refunded   (buyer refunded; verdict failed)
 *
 * @typedef {Object} Hold
 * @property {string} holdId        Unique hold id.
 * @property {string} contractId    Contract this hold backs.
 * @property {string} contractHash  Canonical hash of the contract this hold backs.
 * @property {string} railId        Rail adapter id that owns this hold.
 * @property {number} amount        Held amount.
 * @property {string} currency      Currency/asset code.
 * @property {'held'|'captured'|'refunded'} state Current settlement state.
 * @property {HoldHistoryEntry[]} history Ordered transition log.
 */

// ---------------------------------------------------------------------------
// Extension interface: Verifier
// ---------------------------------------------------------------------------

/**
 * A pluggable delivery verifier. Implementations are pure: given a contract and
 * evidence, return a full Verdict. They must never mutate inputs and must set a
 * clear `reason` on both success and failure.
 *
 * @typedef {Object} Verifier
 * @property {string} name        Stable verifier name (matches predicate.kind).
 * @property {'A'|'B'|'C'} tier   Trust tier this verifier provides.
 * @property {(contract: DeliveryContract, evidence: DeliveryEvidence, opts?: { now?: () => number }) => (Verdict|Promise<Verdict>)} verify
 */

// ---------------------------------------------------------------------------
// Extension interface: RailAdapter
// ---------------------------------------------------------------------------

/**
 * A pluggable settlement rail (escrow mock here; x402 / Stripe MPP / AP2 mandate
 * in production). The adapter owns capture/refund SEMANTICS; DeliveryProof only
 * tells it the decision via a signed receipt.
 *
 * Contract guarantees expected of any adapter:
 *   - authorize(contract) creates a 'held' Hold for the contract price.
 *   - capture(hold, receipt) requires receipt.decision === 'release' and a
 *     currently-'held' hold; otherwise it must reject (no pay on failed verdict).
 *   - refund(hold, receipt) requires receipt.decision === 'refund' and a
 *     currently-'held' hold.
 *   - status(holdId) returns the current Hold.
 *
 * @typedef {Object} RailAdapter
 * @property {string} id
 * @property {(contract: DeliveryContract) => (Hold|Promise<Hold>)} authorize
 * @property {(hold: Hold, receipt: DeliveryReceipt) => (Hold|Promise<Hold>)} capture
 * @property {(hold: Hold, receipt: DeliveryReceipt) => (Hold|Promise<Hold>)} refund
 * @property {(holdId: string) => (Hold|Promise<Hold>)} status
 */

// ---------------------------------------------------------------------------
// Supporting shape schema (used by the schema verifier)
// ---------------------------------------------------------------------------

/**
 * A minimal recursive shape descriptor checked by the schema verifier.
 *
 * @typedef {Object} ShapeSchema
 * @property {'object'|'array'|'number'|'string'|'boolean'} type
 * @property {Object.<string, ShapeSchema>} [properties] For type 'object'.
 * @property {ShapeSchema} [items]                        For type 'array'.
 * @property {string[]} [required]                        Required keys for 'object'.
 */

// No runtime exports: this module is types-only. Importing it is a no-op that
// documents intent and lets tooling resolve the @typedefs above.
export {};
