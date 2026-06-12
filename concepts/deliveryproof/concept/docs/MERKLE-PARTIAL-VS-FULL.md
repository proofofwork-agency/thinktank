# Merkle Partial Mode Versus Full Dataset Verification

DeliveryProof has two dataset paths with different proof scopes:

- `datasetVerifier` checks the delivered dataset itself.
- `datasetMerkleSampleVerifier` checks verifier-selected Merkle samples from a
  committed dataset root.

Partial mode is useful when the verifier should not receive the whole dataset,
but it is intentionally not a shortcut for global dataset truth.

## Decision Table

| Claim | Full `datasetVerifier` | Partial `datasetMerkleSampleVerifier` |
| --- | --- | --- |
| Required columns and row parsing | Yes. The verifier parses the full delivered table and checks required columns. | Only for supplied sample rows. The verifier checks each sample row against the declared row-level column constraints. |
| `rowCount` | Yes. It checks the delivered row count against `rowCount.min` and `rowCount.max`. | No full truth. It requires a committed `rowCount` value and checks proof indices and `proof.leafCount` against that value, but it does not count the whole dataset. |
| `datasetHash` | Yes when committed in `contract.predicate.params.datasetHash` or carried as `evidence.datasetHash`. | No. `datasetHash` is forbidden in partial mode. |
| `uniqueKeys` | Yes. Declared keys must be globally unique across all delivered rows. | No. `uniqueKeys` is forbidden in partial mode. |
| `aggregates` | Yes. Declared `sum`, `distinct`, `min`, `max`, `avg`, and `count` invariants are computed over the delivered rows. | No. `aggregates` is forbidden in partial mode. |
| `sampleDigest` | Yes. The full verifier can check a deterministic verifier-seeded sample digest over rows from the delivered dataset. | No. `sample` and `sampleDigest` are forbidden in partial mode. Partial mode uses Merkle inclusion proofs instead. |
| Merkle root | Optional full-dataset commitment. The full verifier can build the root from the delivered rows and emit proofs for sampled rows. | Required commitment. The verifier checks supplied proofs against the committed root for verifier-selected indices. |
| Whole-table truth | Yes for the declared full-dataset predicates the contract includes. | No. It proves inclusion and sampled-row conformance only. |

## What Partial Mode Proves

`src/verifiers/dataset-merkle-sample.mjs` describes the verifier as:

```text
Tier A partial verifier: Merkle inclusion + sampled-row conformance only.
```

For a passing verdict, the code returns this reason:

```text
partial Merkle sample verified: inclusion + sampled-row conformance only, NOT full-dataset truth
```

The verifier requires:

- `contract.nonce`, used to select sample indices;
- `contract.predicate.params.merkleRoot`;
- `contract.predicate.params.rowCount`;
- `contract.predicate.params.k`;
- row-level `columns`;
- `evidence.merkleSamples` covering exactly the selected indices.

It checks that each supplied sample is selected by the verifier seed, has an
in-range index, has a proof rooted at the committed Merkle root, has
`proof.leafCount` equal to the committed row count, binds `proof.index` and
`sample.index`, hashes the same row as the proof leaf, verifies Merkle inclusion,
and satisfies row-level column constraints.

## Forbidden Global Keys

Partial mode fails closed when the contract attempts to ask it to prove a global
property. The current `FORBIDDEN_GLOBAL_KEYS` list in
`src/verifiers/dataset-merkle-sample.mjs` is:

```js
['uniqueKeys', 'aggregates', 'datasetHash', 'sample', 'sampleDigest', 'format']
```

Those claims belong to `datasetVerifier`, because they require the whole
delivered dataset or a full-dataset commitment check.

## Use The Full Verifier When

- payment depends on exact row count;
- a committed `datasetHash` must match delivered bytes;
- uniqueness must hold globally;
- aggregate totals, counts, averages, minimums, maximums, or distinct counts must
  be proven;
- the buyer needs the verifier to inspect the whole table.

## Use Partial Merkle Mode When

- the seller can commit to a Merkle root;
- the verifier should inspect only selected rows;
- row-level checks on those sampled rows are enough for the contract;
- the buyer accepts that unsampled rows and global properties are not proven by
  this verifier.
