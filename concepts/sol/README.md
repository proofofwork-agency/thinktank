# PageProof — a fail-closed web that can't be taken down

**Status: Concept — research brief (spar phase). Nothing built yet.**

> Serve from the chain with the reach. Verify on the chain with the light client.
> If the page can't prove itself, it doesn't render — and it certainly doesn't get to ask you to sign.

---

## 0. The question

*"Host real webpages / dApps on Solana, Ethereum or Base, with DNS that cannot be shut down.
What protocol or VM extension can we create?"*

Short answer after the research: **don't build a name system, don't build a gateway, and don't
propose a validator-level VM change.** All three are either solved, are the chokepoint itself, or
are a multi-year governance fight for something that doesn't need consensus.

The unoccupied gap is a **fail-closed client** plus an **on-chain commitment format** that makes
every gateway, RPC, and CDN in the path *untrusted and therefore disposable*.

---

## 1. Censorship-resistance is a chain of five links. Everyone fixes one.

| # | Link | Question | Who's shut down in practice |
|---|---|---|---|
| 1 | **Naming** | who maps `foo.eth` → content? | nobody — ENS/SNS ownership is a keypair, genuinely seizure-resistant |
| 2 | **Availability** | where do the bytes live? | pinning services (Pinata/Infura/web3.storage dashboards), gateway blocklists |
| 3 | **Integrity** | were the bytes swapped? | *unhandled almost everywhere* |
| 4 | **Last mile** | how does a normal browser get them? | **this is where everything dies** — DNS, TLS, registrar, ISP |
| 5 | **Execution** | how does the dApp read/write chain state? | RPC providers (OFAC filtering, geoblocking) |

Link 1 is fine. Link 4 is where the corpses are, and 2024–2026 gave us the proof:

- **Feb 2026** — Verizon's DNS began blocking *all* `eth.limo` domains. One carrier, one config
  change, every ENS site dark for those users.
- **Apr 2026** — `eth.limo`'s registrar account at easyDNS was socially engineered; the attacker
  controlled wildcard `*.eth.limo`. Vitalik publicly told people to stop visiting any eth.limo URL.
  ENS records were perfect. IPFS content was perfect. The *last mile* was owned.
- **Aug 2024** — Brave removed native IPFS support (<0.1% usage). The "browsers will just support
  it" path is closed.
- **Jun 2026** — Namecheap exited Handshake TLDs entirely after selling Namebase. Handshake was the
  only real ICANN-root replacement. **Building a new name system is a dead road — don't.**

The lesson is not "we need a more decentralized gateway." **You cannot decentralize a chokepoint.
You can only make it not matter.** It stops mattering the moment the client verifies bytes itself:
then gateways are interchangeable, disposable, and blocking one costs the adversary a permanent
resource to gain five minutes.

---

## 2. Prior art — what exists, what it actually solves

| System | Solves | Doesn't |
|---|---|---|
| **ERC-4804 / ERC-6860** `web3://` | links 2+3 on EVM: the page *is* contract state | browsers don't speak it → back through a gateway → link 4 broken |
| **ERC-5219 / ERC-6944** | HTTP-shaped `request()` on a contract; real server semantics | same |
| **EthStorage + Colibri** | **the best existing piece.** L1 stores only the EIP-4844 KZG versioned hash; the client re-derives it from gateway bytes. WASM verifier, ~0.45× download time overhead | it's a **badge, not a gate** — fail-open. And Ethereum-only |
| **Helios (a16z)** | link 5, properly: 5.3 MB WASM multichain light client, **supports OP Stack → Base** | not wired to content delivery |
| **@helia/verified-fetch + IPFS service-worker gateway** | trustless CID verification *inside the browser*, no extension | IPFS-only; availability still depends on who pins |
| **ENS / SNS** | link 1, well | resolution to a browser needs eth.limo / sol-domain.org / 4sol.xyz — link 4 again |
| **Solana Actions / Blinks** | great distribution surface | **actions are hosted on ordinary HTTPS**, and unfurling requires the **Dialect registry** — a trusted centralized allowlist |
| **ERC-7754 (TWIST)** | **closest prior art.** Wallet verifies a signed request against a dapp's published key before signing — exactly the right *place* to intervene | roots trust in **DNS TXT + TLS** (the link-4 chokepoint it should be escaping), and is **explicitly fail-open**: unsigned request ⇒ "SHOULD display a visible and actionable warning," user may proceed. Draft |
| **IPFS Dapps WG** (Shipyard + Liquity) | names the identical problem — "users are unknowingly trusting a gateway"; goal is verified retrieval as the norm | IPFS-only; verifying a *frontend* CID still effectively requires running a node. No capability gating |
| **Handshake** | link 4, genuinely | in structural decline; do not build on it |

**The pattern: every one of these is fail-open.** If verification is unavailable, impossible, or
just not implemented, you get the page anyway. That is the bug.

**And Solana has essentially none of it.** No `web3://` equivalent, no production light client
(Tinydancer is still at SPV/DAS on a three-phase roadmap), name resolution goes through gateways,
and Blinks substitute a registry for cryptography. That's the opening.

---

## 3. The reframe: the "VM extension" is client-side, not validator-side

The instinct is to write a SIMD adding syscalls so validators can serve HTTP. Wrong move.

**Serving a page is a read. Reads never need consensus.**

So the extension isn't to the validator's VM — it's an extension of *the VM's reach, down into the
browser*. Three consequences, all good:

1. **No SIMD, no hard fork, no governance.** Ship it as a library and an sRFC for the data format.
2. **Solana's account model is a better fit than the EVM's.** On Ethereum, reading a site is an
   `eth_call` — an *execution* you must trust or prove. On Solana a static site is literally account
   bytes: one `getMultipleAccounts`. No execution to verify at all.
3. **Every wallet already holds an RPC connection.** Which means: *if you can use a Solana wallet,
   you can load the site.* Blocking the site requires blocking Solana RPC.

For dynamic pages, define a **read-only SVM profile** (the Solana analogue of ERC-5219): a program
entrypoint invoked as a pure function of `(pinned slot, account set, request path) → (status, body,
headers)`, with no signers, no writes, no CPI outside a read allowlist, no wall-clock. Pure and
deterministic ⇒ **re-executable client-side** in a WASM build of the sBPF interpreter. That
re-executability is the entire point: it's what lets the client check the gateway's answer instead
of believing it.

---

## 4. Proposal: **PageProof**

Two artifacts. Everything else is commodity.

### 4.1 PPM — the PageProof Manifest (the format)

A small on-chain object, the site's only trust anchor:

```
version, site_id
root            : merkle root over {path → (content_hash, size, mime, encoding)}
mode            : static | read-svm
program         : (read-svm only) program id + pinned account set
routes[]        : ordered retrieval hints — solana-account | evm-sstore2 | ethstorage-blob
                  | arweave | ipfs | https-mirror     ← all UNTRUSTED, all verified against `root`
anchors[]       : (chain_id, address/slot) where this manifest hash is also committed
min_proof_level : the floor this site refuses to render below
revocation      : key that can burn a compromised version
```

Two properties do the work:

- **Routes are untrusted.** They're performance hints, not authority. Anyone may add a mirror
  permissionlessly; nobody's mirror can lie. Censoring means killing *every* route while new ones
  cost nothing to add. That's an asymmetry that finally runs the right direction.
- **`root` is the only thing that must be authentic** — a few hundred bytes. Cheap to put anywhere,
  cheap to replicate, cheap to cross-anchor.

### 4.2 The fail-closed loader (the client)

Four proof levels, and — the part nobody else does — **capability is bound to proof level**:

| Level | How it was established | What the page may do |
|---|---|---|
| 0 `unverified` | nothing checked | **nothing. Blank page + named reason.** |
| 1 `quorum` | N independent RPCs agree byte-for-byte on the account/state hash | render read-only; **wallet signing blocked** |
| 2 `verified` | light-client proof to a chain header (Helios for Base/ETH; cross-anchor for Solana) | render + sign |
| 3 `anchored` | level 2 on ≥2 independent chains | render + sign + green badge |

> **This is DeliveryProof's invariant, moved one layer up.** DeliveryProof: *no capture on a failing
> verdict.* PageProof: **no signing prompt on an unproven frontend.** Same house thesis, new surface.

And it's not a purity argument — it's the highest-value security feature in crypto right now. The
frontend swap is *the* drain vector; EthStorage pitches `web3://` directly against the $1.5B Bybit
frontend attack. A wallet that can refuse to sign against an unproven frontend has a product reason
to ship this. **That's the distribution wedge: not browsers, wallets.** Chrome will never ship
`sol://`. Phantom, Backpack, MetaMask and Rabby already ship in-app browsers, already hold the RPC,
and already own the liability. And nobody's ISP can remove an installed extension.

---

## 5. The strongest idea in here: cross-anchoring

Solana's blocker is real and I won't paper over it: **there is no production Solana light client.**
Verifying "account X held bytes B at slot N" means verifying ≥2/3 of stake-weighted votes —
a large stake table and ~1000 Ed25519 verifications. Tinydancer is working exactly this and isn't
ready.

So don't wait for it. **Verify on the chain that has a light client; serve from the chain that has
the reach.**

- Bytes live in Solana accounts — cheap parallel reads, and every wallet is already connected.
- The manifest hash is *also* written to Base (an OP Stack chain **Helios already supports**, in
  5.3 MB of WASM, in a browser, today).
- The client verifies the commitment against Base via Helios, then verifies the Solana-served bytes
  against that commitment.

Solana's missing light client is routed around entirely, and the security floor becomes
Ethereum's. When Tinydancer lands, it upgrades level 2 to native and the format doesn't change.
I have not found anyone doing this for frontends.

---

## 6. The bootstrap problem — the honest limit

If the adversary controls the network, where does the *loader* come from? There is no cryptographic
escape from this. Every trust chain terminates in something the human holds. Be honest and make the
root as small as possible:

1. A **~2 KB self-verifying shell**: fetch loader → hash it → compare against a hash literal baked
   into the shell → refuse on mismatch. It can therefore be served by *anyone, including the
   adversary*.
2. The **loader is small (<100 KB target) and reproducibly built**, so its hash is independently
   confirmable, publishable everywhere, and recoverable from chain.
3. It ships **inside wallets** for everyone who doesn't want to think about any of this.

One human-held root (a pinned hash: in the wallet, a bookmark, on paper). Everything downstream is
cryptography. Claiming less than that is dishonest; claiming more is impossible.

---

## 7. Costs — measured, not vibed

| Where | Price | Permanence | Verdict |
|---|---|---|---|
| Solana account | ~7 SOL / MiB, **fully refundable on close** (3480 lamports/byte/yr × 2 yr exemption) | permanent while funded | ~1.4 SOL for a 200 KB bundle. Fine for the hot tier. Max account 10 MiB; growth capped at 10,240 bytes per realloc |
| Base / L2 blob | ~$3.83/MB (early-2026 L2 blob rate) | **pruned ~18 days** | commitment only, never content |
| EVM contract (SSTORE2) | expensive on L1, viable on L2 | permanent | good for the manifest |
| EthStorage | small fraction of L1 | L2-backed, L1-committed | best EVM bulk tier |
| Arweave / IPFS | cheap | pay-once / pin-dependent | bulk tier — **untrusted, hash-verified** |

Which forces the tiering, and the tiering is the design:

- **Hot tier** — bootloader + manifest, a few KB. On-chain. Tens to low hundreds of dollars,
  refundable. *This is the only part that must be uncensorable.*
- **Bulk tier** — everything else, anywhere, verified against the manifest. **Storage becomes a
  commodity you can swap on a bad day.**

---

## 8. On MiCA — straight, then moving on

The transitional period ended **1 July 2026**. MiCA's decentralization exemption turns on whether
an identifiable person controls governance, the front-end, fees, or upgrade keys — and supervisors
explicitly look at front-ends, hosting, and gateway sites as the points of contact.

So: removing the hosted front-end removes one of the control points regulators look for, and that's
a real effect. But it is **not** a liability escape. Hold upgrade keys, take fees, or be the
identifiable operator and you're a CASP regardless of where the HTML lives.

Treat this as an **availability-and-integrity** project. It's a good one on those merits — the
eth.limo hijack and the Verizon block hit people who had done nothing wrong and had no recourse.
That's the problem worth solving.

---

## 9. What we build first (the falsifiable prototype)

**Thesis:** *A normal user, on a normal browser, can load a page whose bytes no single party can
alter or withhold — and the client can tell the difference and act on it.*

Kill-or-prove demo, three scenes:

1. **Tamper** — hostile gateway flips one byte in the JS bundle. Loader refuses to render and names
   the file. (Every system in §2 renders it.)
2. **Withhold** — kill the gateway entirely. Loader loads via a different route with no config
   change and no trust migration.
3. **Downgrade** — drop from level 2 to level 1. The page renders; the *sign button is dead*.

Scope: Solana static tier + Base cross-anchor + Helios, `read-svm` deferred to v2.

**Named weakest leg** (house rules): **v0 "verification" on the Solana side is RPC quorum diversity
— a trust assumption dressed as a check.** Cross-anchoring to Base is the actual fix and it is
unbuilt and untested. If the cross-anchor round-trip turns out too slow or too expensive to sit in
the page-load path, the concept degrades to "a somewhat better gateway" and should be killed.

Second-weakest: the bootstrap root (§6) is irreducible. Anyone claiming otherwise is selling
something.

---

## 10. Do not build

- **A new name system.** ENS and SNS already win at link 1. Handshake's 2026 collapse is the
  evidence for what happens to the alternative.
- **Another gateway.** That's the chokepoint. Make it irrelevant instead.
- **A validator-level SIMD / new syscall.** Reads don't need consensus (§3).
- **Another pinning service.** Bulk storage should be a commodity, not a dependency.

---

## 11. Adjacent shot: fix Blinks

Solana Actions require the **Dialect registry** — a trusted centralized allowlist deciding which
blinks unfurl. Same disease, smaller surface: a trusted third party standing where a hash should be.
A PPM-shaped manifest lets a blink client verify action metadata against on-chain bytes instead of
asking permission. Small, self-contained, ecosystem-relevant, and a plausible Solana Foundation
pitch — a good second prototype, or a good first one if PageProof proper is too big a bite.

---

## Sources

- [ERC-4804](https://eips.ethereum.org/EIPS/eip-4804) · [ERC-6860](https://eips.ethereum.org/EIPS/eip-6860) · [ERC-5219](https://eips.ethereum.org/EIPS/eip-5219) · [ERC-6944](https://eips.ethereum.org/EIPS/eip-6944)
- [EthStorage: Client-Side Verification for On-Chain Frontends](https://blog.ethstorage.io/client-side-verification-for-on-chain-frontends/) · [Avoiding the $1.5B Bybit Attack with web3://](https://blog.ethstorage.io/avoiding-the-1-5-billion-bybit-attack-with-web3/)
- [Helios multichain light client](https://github.com/a16z/helios) · [ethereum.org: light clients](https://ethereum.org/developers/docs/nodes-and-clients/light-clients/)
- [@helia/verified-fetch](https://github.com/ipfs/helia-verified-fetch) · [IPFS service-worker gateway](https://github.com/ipfs/service-worker-gateway) · [Verified IPFS retrieval in browsers](https://blog.ipfs.tech/verified-fetch/)
- [easyDNS: the eth.limo hijack is on us](https://easydns.com/blog/2026/04/18/we-screwed-up-and-we-own-it-the-eth-limo-shtshow-is-on-us/) · [The Block: easyDNS accepts responsibility](https://www.theblock.co/post/398005/easydns-accepts-responsibility-for-eth-limo-hijack-its-first-social-engineering-breach-in-28-years) · [eth.limo Q1 2026 update](https://discuss.ens.domains/t/eth-limo-q1-2026-update/22082)
- [Namecheap exits Handshake TLDs](https://webhosting.today/2026/06/11/namecheap-ends-handshake-tld-support-as-web3-domain-projects-retreat/) · [Handshake FAQ](https://handshake.org/faq/)
- [Brave: IPFS support](https://brave.com/blog/ipfs-support/)
- [Solana Actions and Blinks](https://solana.com/developers/guides/advanced/actions) · [sRFC 31: Blinks/Actions compatibility](https://forum.solana.com/t/srfc-31-compatibility-of-blinks-and-actions/1892)
- [Tinydancer docs](https://docs.tinydancer.io/) · [Tinydancer whitepaper](https://www.tinydancer.io/whitepaper.pdf) · [Anza: simple payment and state verification](https://docs.anza.xyz/proposals/simple-payment-and-state-verification)
- [Anza: the Solana eBPF virtual machine](https://www.anza.xyz/blog/the-solana-ebpf-virtual-machine) · [solana_rbpf docs](https://docs.rs/solana_rbpf/)
- [RareSkills: Solana account rent and storage cost](https://rareskills.io/post/solana-account-rent) · [QuickNode: understanding rent](https://www.quicknode.com/guides/solana-development/getting-started/understanding-rent-on-solana)
- [SNS domain records](https://docs.sns.id/dev/domain-records) · [SNS web resolution](https://sns.guide/domain-name/web-resolution.html)
- [Infura and Alchemy blocking Tornado Cash](https://www.theblock.co/post/162402/infura-and-alchemy-blocking-access-to-tornado-cash)
- [Are frontends regulated under MiCA? (Axis Advisory)](https://www.axisadvisory.xyz/blog-posts/are-frontends-interfaces-regulated-under-mica) · [Hacken: MiCA 2026 compliance](https://hacken.io/discover/mica-regulation/)
- [L2 blob economics, early 2026](https://blockeden.xyz/blog/2026/01/16/celestia-blob-economics-data-availability-rollup-costs/)
