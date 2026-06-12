# Human Decision Register

These items require explicit human approval before implementation or production
use. They are outside the scope of the reference library.

## Real Custody, MSB, MTL, Tax, And Consumer Obligations

Any deployment that controls funds, intermediates payments, stores customer
balances, operates escrow, or presents as a payment service needs qualified legal
review before launch.

Questions for counsel and operators include:

- whether the deployment is custodial or non-custodial;
- money services business registration;
- state money-transmitter licensing;
- sanctions screening, KYC, AML, and record retention;
- tax reporting;
- consumer protection, chargeback, and dispute obligations;
- terms of service and jurisdiction-specific risk.

DeliveryProof does not answer these questions. It produces signed delivery
justification records for a rail to consume.

## Live On-Chain RPC And Transaction Submission

Any code that signs transactions, submits to a chain, manages RPC credentials,
manages gas, or controls wallets requires a separate go/no-go.

Before enabling live chain actions, decide:

- which chain and settlement contract are in scope;
- who controls keys and signer policy;
- how transaction simulation, nonce management, gas limits, and reorg handling
  work;
- whether RPC credentials are allowed in CI or local agent environments;
- how failures, partial finality, and replay are reported to operators.

The current ERC-8004 and ERC-8183 helpers are thin receipt projection utilities.
They can emit ABI-shaped argument bytes, but they do not perform chain calls,
wallet actions, RPC, private-key handling, or submission.

## External Operator Security Review

Before real money, customer data, or regulated workflows are handled by a
deployment, obtain an external security review of the whole integration, not only
this library.

The review should cover:

- rail adapter authorization and idempotency;
- replay store atomicity and durability;
- key custody, rotation, revocation, and incident response;
- audit logging and dispute retrieval;
- verifier resource bounds under production inputs;
- dependency and deployment supply-chain controls;
- operational runbooks for settlement failures.

## Not In This Register

Keccak and ABI projection helpers are in the library. Live transaction
submission, wallet control, provider/RPC wiring, and custody-adjacent behavior
remain in this register.
