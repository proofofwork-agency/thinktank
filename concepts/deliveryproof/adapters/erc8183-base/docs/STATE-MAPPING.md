# State Mapping: DeliveryProof Hold ⇄ ERC-8183 Job

This adapter is the ERC-8183 ("Agentic Commerce") **evaluator**. It projects the
DeliveryProof Hold state machine (`held → captured | refunded`) onto the ERC-8183
Job lifecycle and back. **TESTNET / LOCAL ONLY** — no mainnet, no custody, no
finality guarantee.

The single source of truth for this mapping in code is
[`../src/job-status.mjs`](../src/job-status.mjs) (`JobStatus`,
`mapJobStatusToHoldState`, `isSettleable`, `isTerminal`).

## The ERC-8183 Job lifecycle

```text
Open ──fund──▶ Funded ──submit──▶ Submitted ──▶ Completed   (evaluator: complete)
                                          │
                                          ├──▶ Rejected    (evaluator: reject)
                                          └──▶ Expired      (deadline passed)
```

The Client funds the job and the Provider submits work. ONLY the Evaluator may
move a `Submitted` job to `Completed` (`complete(jobId)`, release escrow to the
provider) or `Rejected` (`reject(jobId)`, refund the client). `Expired` is reached
when the job's deadline passes without an evaluator decision; the escrowed budget
returns to the client.

DeliveryProof occupies the Evaluator slot. It does **not** fund, submit, or own
the job.

## Job status → Hold state

| ERC-8183 Job status | DeliveryProof Hold state | Meaning |
|---------------------|--------------------------|---------|
| `Open` | `held` | Job exists, not yet funded. Escrow not terminalized. |
| `Funded` | `held` | Escrow deposited, work not yet submitted. |
| `Submitted` | `held` | Work submitted; **the only state the evaluator may act on**. |
| `Completed` | `captured` | Escrow released to the provider. |
| `Rejected` | `refunded` | Escrow refunded to the client. |
| `Expired` | `refunded` | Deadline passed; escrowed budget returned to the client. |

`Expired` maps to `refunded` because an expired job returns its budget to the
client — the **same money outcome** as an explicit rejection. The adapter reports
it as `refunded` so a Hold-state consumer sees a consistent terminal picture.

Helper semantics:

- `isSettleable(status)` is `true` **only** for `Submitted`.
- `isTerminal(status)` is `true` for `Completed`, `Rejected`, and `Expired`.
- `mapJobStatusToHoldState(status)` is total over the six known statuses and
  throws `Erc8183RailError` on any unknown status (it never silently defaults).

## RailAdapter op → ERC-8183 action

| RailAdapter op | ERC-8183 action | Notes |
|----------------|-----------------|-------|
| `authorize(contract)` | read `getJob`, **attach** | Assert `Submitted`, synthesize a `held` Hold. No funding, no submission. |
| `capture(hold, releaseReceipt)` | `complete(jobId, reason)` | Release escrow to the provider. `reason` = receipt commitment. |
| `refund(hold, refundReceipt)` | `reject(jobId, reason)` | Refund the client. `reason` = receipt commitment. |
| `status(hold)` | `getJob(jobId)` | Map the live Job status with the table above. |

The `reason` (a `bytes32` digest of the signed receipt) and the
`complete`/`reject` direction come from the core projection
`toErc8183EvaluatorResult(receipt, { jobId, hashAlg })`, wrapped by the adapter's
`deliveryReceiptToEvaluatorCall`.

## The `authorize` attach seam

`authorize` is an **attach**, not a create. This is the key honesty point of the
adapter.

A normal escrow rail's `authorize` *creates* a hold and reserves funds. This
adapter cannot and must not: ERC-8183 funding and the Open→Funded→Submitted
transitions are performed by the Client and Provider, outside DeliveryProof. So
`authorize` instead:

1. Resolves a `jobId` from the contract via `jobIdResolver(contract)` (default:
   `contract.jobId ?? contract.predicate?.params?.jobId ?? contract.idempotencyKey
   ?? contract.id`).
2. Reads the live job with `getJob(jobId)`.
3. If no job exists → throws `Erc8183JobNotFoundError` (the adapter never funds or
   creates a job; an absent job is an operator/config error).
4. If the job's status is not `Submitted` → throws `Erc8183NotSettleableError`
   (with `jobId` and `status` attached). `Open`/`Funded` are not yet ready;
   `Completed`/`Rejected`/`Expired` are already terminal.
5. Otherwise synthesizes a `held` Hold whose `amount` and `currency` come from the
   job (`getJob` is authoritative for the money fields, not the contract), bound
   to the contract id and hash and to this rail's id.

The synthesized Hold id is deterministic:

```text
holdId = "erc8183:" + chainNamespace + ":" + jobContractAddress + ":" + jobId
```

so the same job under the same operator config always yields the same Hold id —
which is what makes idempotency-via-`getJob` and same-receipt replay detection
work across restarts.

### Why amount/currency come from `getJob`

The on-chain job's escrowed budget is the real money. The adapter binds the Hold's
`amount`/`currency` to what `getJob` reports, then the 7-field receipt⇄hold binding
in `capture`/`refund` requires the receipt to agree. A receipt whose `amount`/
`currency` disagrees with the funded job is rejected before any `complete`/`reject`
submission.

## Idempotency via `getJob` (not a trusting fake)

Because the adapter does not own the escrow, it cannot rely on its own in-memory
terminals map alone — a different process, a retry, or a restart may have already
submitted the evaluator decision. So **before submitting any transaction**, the
rail reconciles against live chain state:

1. **Exact replay short-circuit.** A terminals `Map` keyed
   `"<holdId>:<release|refund>:<receiptHash>"` returns the prior terminal Hold for
   an identical re-submission with no chain call.
2. **Reconcile via `getJob`.** Read the live job:
   - already `Completed` and this is a **capture** → return the `captured` Hold,
     **no tx** (idempotent — the provider was already paid).
   - already `Rejected` (or `Expired`) and this is a **refund** → return the
     `refunded` Hold, **no tx** (idempotent — the client was already refunded).
   - **opposite terminal** (e.g. job is `Completed` but this is a refund, or
     `Rejected`/`Expired` but this is a capture) → **throw a conflict**. The chain
     has already decided the other way; the adapter must not contradict it.
   - still `Submitted` → proceed to submit `complete`/`reject`.

This makes the on-chain job status the authority for "did this already happen?",
which is the only correct answer when the adapter is not the custodian. The
in-memory reference client deliberately **throws** on a second `complete`/`reject`
of a terminal job precisely so the rail's idempotency must come from this
reconcile path and is genuinely exercised, not masked by a lenient fake.

## Reorg stance

The adapter makes **no exactly-once and no finality guarantee**.

- A `txRef` returned by `complete`/`reject` is a submission reference, not a proof
  of final settlement. Whether and when that transaction is final is a property of
  the chain and the operator's confirmation policy, not of this adapter.
- A reorg can revert a previously observed `Completed`/`Rejected` status back to
  `Submitted`. The adapter's reconcile-via-`getJob` reflects whatever the chain
  currently reports; it does not pin a remembered terminal state against a reorg.
  If the operator's policy requires it, re-running `capture`/`refund` after a
  reorg will re-evaluate live state and may re-submit.
- Detecting reorgs, choosing a confirmation depth, and deciding how to respond to
  a reverted terminal are **operator policy**, enumerated in
  [../ESCALATIONS.md](../ESCALATIONS.md). The adapter intentionally does not bake
  in a finality model, because the correct one is chain- and operator-specific.

In short: the adapter is a faithful, idempotent-on-live-state evaluator that
mirrors the core money-safety invariants at the ERC-8183 boundary. It is not a
settlement-finality oracle, and it does not pretend to be one.
