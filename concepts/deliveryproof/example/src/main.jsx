import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const scenarios = {
  dataset: {
    label: 'Dataset delivery',
    title: 'Pay for a clean customer dataset',
    buyer: 'Buyer wants 1,000 customer rows with valid IDs, regions, and revenue numbers.',
    sellerGood: 'Seller submits a dataset that matches the contract.',
    sellerBad: 'Seller submits a schema-valid dataset with corrupted revenue values.',
    contractRules: [
      'Required columns: id, region, revenue',
      'Revenue must be a number in the agreed range',
      'Merkle proofs must match the committed dataset root',
      'No payment release on a negative verdict',
    ],
    goodChecks: [
      ['Schema shape', true, 'All required columns are present.'],
      ['Value rules', true, 'Every sampled row satisfies type, domain, and range rules.'],
      ['Merkle inclusion', true, 'Sampled rows belong to the committed dataset root.'],
      ['Signed verdict', true, 'DeliveryProof signs release evidence for the rail.'],
    ],
    badChecks: [
      ['Schema shape', true, 'A shallow checker would stop here and pay.'],
      ['Value rules', false, 'Revenue values fail the objective contract.'],
      ['Merkle inclusion', true, 'Rows may be included, but they still fail row rules.'],
      ['Signed verdict', false, 'DeliveryProof signs a refund verdict instead.'],
    ],
  },
  api: {
    label: 'API response',
    title: 'Pay for the right API answer',
    buyer: 'Buyer pays an agent to call a weather API for Amsterdam.',
    sellerGood: 'Seller returns HTTP 200 with the required city and temperature fields.',
    sellerBad: 'Seller returns HTTP 200 and valid JSON, but for the wrong city.',
    contractRules: [
      'Status must be 200',
      'JSON must include city and temperature',
      'city must equal Amsterdam',
      'Response must bind to the contract nonce',
    ],
    goodChecks: [
      ['HTTP success', true, 'The response is 200 OK.'],
      ['JSON shape', true, 'The required fields are present.'],
      ['Business field', true, 'The city is exactly Amsterdam.'],
      ['Signed verdict', true, 'The rail can release payment.'],
    ],
    badChecks: [
      ['HTTP success', true, 'The response is 200 OK.'],
      ['JSON shape', true, 'The JSON is valid and shaped correctly.'],
      ['Business field', false, 'The city is Rotterdam, not Amsterdam.'],
      ['Signed verdict', false, 'DeliveryProof prevents blind payment.'],
    ],
  },
  document: {
    label: 'Document',
    title: 'Pay for a structured report',
    buyer: 'Buyer orders a Markdown report with required sections and checksums.',
    sellerGood: 'Seller submits the required sections, terms, links, and checksums.',
    sellerBad: 'Seller submits a nice-looking report missing the required Risk section.',
    contractRules: [
      'Required heading: Risk',
      'Required term: refund policy',
      'Allowed links only',
      'Section checksum must match',
    ],
    goodChecks: [
      ['Markdown parse', true, 'The document is valid Markdown.'],
      ['Required structure', true, 'All required headings and terms exist.'],
      ['Checksum', true, 'The committed section bytes match.'],
      ['Signed verdict', true, 'Payment can be released.'],
    ],
    badChecks: [
      ['Markdown parse', true, 'A plain text checker would accept it.'],
      ['Required structure', false, 'The Risk section is missing.'],
      ['Checksum', false, 'The committed section bytes cannot match.'],
      ['Signed verdict', false, 'DeliveryProof refunds instead of judging prose quality.'],
    ],
  },
};

const glossary = {
  rail: 'Stripe, x402, or another payment rail moves money. DeliveryProof only decides whether the delivery passed.',
  proof: 'A proof is a reproducible check: hash, schema, field rule, signature, test result, or Merkle inclusion.',
  merkle: 'A Merkle proof shows a row belongs to a committed dataset root without needing to reveal the whole dataset.',
  receipt: 'The receipt is signed evidence of why the money was released or refunded.',
  scope: 'DeliveryProof proves objective delivery. It does not judge subjective quality unless a trusted oracle signs that judgment.',
  keyring: 'A keyring lets verifyReceipt() trust more than one settlement key at once, so you can rotate signing keys without breaking old receipts. Verification only — signing still uses one active key.',
  rotation: 'Key rotation = retire an old signing key and start signing with a new one. Receipts signed by the old key must still verify, so verifiers accept a set of trusted keys.',
  auditbundle: 'An audit bundle collates a receipt, its contract, evidence hashes, and rail status into one inspectable object so a dispute handler can re-check the bindings. It is an inspection aid, not a new proof.',
  keccak: 'Ethereum uses keccak256, which is NOT the same bytes as the NIST sha3-256 built into Node. v0.9 adds a real keccak256 helper so receipts can project onto EVM-style hashes — projection only, no chain submission.',
  conformance: 'A conformance suite is a reusable test any third-party rail or replay-store adapter runs to self-certify it upholds the safety rules (binding, terminality, idempotency) before touching real money.',
  dependency: 'Through v0.8 DeliveryProof had zero dependencies. v0.9 adds exactly one audited, pinned runtime dependency — @noble/hashes@2.2.0 — only for Ethereum keccak/ABI helpers. A CI allowlist guard fails on any other package or transitive.',
};

// v0.9 production-integration seams. These are not "good vs bad delivery"
// money-shots; they are the wiring that makes the protocol safe to integrate.
// Every value here mirrors the verified v0.9 behavior in the library.
const seams = {
  keyring: {
    label: 'Key rotation',
    title: 'Rotate signing keys without breaking old receipts',
    info: 'keyring',
    summary:
      'verifyReceipt() now accepts a single PEM (unchanged) or a keyring of trusted keys. Receipts signed by a retired key keep verifying after you rotate to a new one.',
    bullets: [
      'PEM-string path is byte-identical to before — no breaking change',
      'A keyring verifies receipts signed by ANY trusted key',
      'An unknown signer key returns false (never throws)',
      'Verification only — signing still uses one active key',
    ],
    terminal: [
      { kind: 'muted', text: '$ rotate settlement keys, keep verifying old receipts' },
      { kind: 'json', text: "oldReceipt.signerKeyId = '8f1c…' (signed by key A)" },
      { kind: 'ok', text: "verifyReceipt(oldReceipt, keyA_pem) = true   // pre-rotation path unchanged" },
      { kind: 'info', text: 'rotate(): active signing key A -> key B' },
      { kind: 'ok', text: "verifyReceipt(oldReceipt, { keys: [keyA, keyB] }) = true   // old receipt still trusted" },
      { kind: 'ok', text: "verifyReceipt(newReceipt, { keys: [keyA, keyB] }) = true   // new receipt trusted too" },
      { kind: 'fail', text: "verifyReceipt(oldReceipt, { keys: [strangerKey] }) = false   // unknown signer rejected" },
    ],
    foot: 'Real KMS/HSM signing is a documented interface (companion package); the core ships verification + an in-memory keyring helper only.',
  },
  audit: {
    label: 'Audit bundle',
    title: 'Hand a dispute handler one inspectable object',
    info: 'auditbundle',
    summary:
      'buildAuditBundle() collates the receipt, contract, evidence hashes, route decision and rail status, with explicit match booleans so tampering shows up as a mismatched binding.',
    bullets: [
      'Pure assembly + hashing — no telemetry, no network, no settlement change',
      'Re-checks that receipt, contract, evidence and rail status all bind',
      'Any tampered field flips a match boolean to false',
      'It is an inspection aid, not a new cryptographic proof',
    ],
    terminal: [
      { kind: 'muted', text: '$ buildAuditBundle({ receipt, contract, evidence, railStatus })' },
      { kind: 'ok', text: 'contractHash matches receipt.contractHash      = true' },
      { kind: 'ok', text: 'evidenceHash matches receipt.evidenceHash      = true' },
      { kind: 'ok', text: 'routeDecision present and signed                = true' },
      { kind: 'ok', text: 'railStatus bound to hold/amount/currency       = true' },
      { kind: 'muted', text: '— now tamper one byte of the evidence —' },
      { kind: 'fail', text: 'evidenceHash matches receipt.evidenceHash      = false   // mismatch surfaces' },
    ],
    foot: 'The bundle does not re-decide anything; it makes the existing signed bindings easy for an auditor to re-verify.',
  },
  keccak: {
    label: 'Keccak / EVM',
    title: 'Project a receipt onto Ethereum-style hashes',
    info: 'keccak',
    summary:
      'Interop projections can opt into hashAlg "keccak256" to emit real Ethereum keccak digests, instead of the default sha256. Projection only — no wallet, RPC, or chain submission.',
    bullets: [
      'sha256 stays the DEFAULT (backward compatible)',
      "keccak256 is REAL Ethereum keccak — not Node's NIST sha3-256",
      'ABI-shape encoding of the projection payload, no calldata/selectors',
      'No chain submission, no private keys, no provider — projection only',
    ],
    terminal: [
      { kind: 'muted', text: '$ toErc8004ValidationPayload(receipt, { hashAlg })' },
      { kind: 'info', text: "keccak256('') = c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470" },
      { kind: 'muted', text: "node sha3-256('') = a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a" },
      { kind: 'ok', text: 'keccak256 != sha3-256  // proven distinct; the dependency is justified' },
      { kind: 'json', text: "hashAlg: 'sha256'    -> responseHash = 0x<sha256(receipt)>   (default)" },
      { kind: 'json', text: "hashAlg: 'keccak256' -> responseHash = 0x<keccak256(receipt)> (opt-in)" },
    ],
    foot: 'On-chain submission stays out of scope (chain secrets = custody-adjacent). v0.9 added exactly one audited dependency, @noble/hashes, for this.',
  },
  conformance: {
    label: 'Conformance',
    title: 'Let any rail or store self-certify before real money',
    info: 'conformance',
    summary:
      'Exported conformance suites let a third-party rail adapter or durable replay store prove it upholds the safety rules — so an integrator cannot wire an unsafe adapter by accident.',
    bullets: [
      'Rail suite: receipt↔hold binding, terminality, no-capture-on-refund, no cross-hold replay, idempotency',
      'Replay-store suite: reserve-once, survive-restart, reject-replay, reject-concurrent-double-reserve',
      'Runs in the integrator’s own test runner — reads rail.id, certifies ANY adapter',
      'Deliberately-broken adapters fail the suite (the suite has teeth)',
    ],
    terminal: [
      { kind: 'muted', text: '$ runRailConformance({ createRail })' },
      { kind: 'ok', text: 'PASS authorize-creates-held' },
      { kind: 'ok', text: 'PASS receipt-hold-binding-7-fields' },
      { kind: 'ok', text: 'PASS no-capture-on-refund-decision' },
      { kind: 'ok', text: 'PASS no-cross-hold-receipt-replay' },
      { kind: 'ok', text: 'PASS idempotent-recapture' },
      { kind: 'fail', text: 'a rail that captures on a refund receipt -> FAILS no-capture-on-refund-decision' },
    ],
    foot: 'Real Stripe/x402/Postgres/Redis/KMS adapters live in a companion package that depends on this core and runs these suites in its own CI.',
  },
};

function App() {
  const [scenarioKey, setScenarioKey] = useState('dataset');
  const [delivery, setDelivery] = useState('good');
  const [stage, setStage] = useState(6);
  const [payloadTab, setPayloadTab] = useState('contract');
  const [seamKey, setSeamKey] = useState('keyring');
  const scenario = scenarios[scenarioKey];
  const checks = delivery === 'good' ? scenario.goodChecks : scenario.badChecks;
  const passed = checks.every((check) => check[1]);
  const terminalLines = useMemo(
    () => buildTerminalLines({ scenarioKey, scenario, delivery, checks, passed, stage }),
    [scenarioKey, scenario, delivery, checks, passed, stage],
  );

  const visibleChecks = useMemo(() => checks.slice(0, Math.max(0, stage - 1)), [checks, stage]);

  function runDemo(nextDelivery = delivery) {
    setDelivery(nextDelivery);
    setStage(0);
    const timers = [1, 2, 3, 4, 5, 6].map((value) =>
      window.setTimeout(() => setStage(value), value * 520),
    );
    return () => timers.forEach(window.clearTimeout);
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">DeliveryProof interactive demo</p>
            <h1>Proof-based release or refund</h1>
          </div>
          <div className="rail-pill">
            Stripe / x402 rail
            <Info term="rail" />
          </div>
        </header>

        <div className="control-row" aria-label="Scenario controls">
          {Object.entries(scenarios).map(([key, item]) => (
            <button
              key={key}
              className={key === scenarioKey ? 'segment active' : 'segment'}
              onClick={() => {
                setScenarioKey(key);
                setStage(6);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>

        <section className="deal-band">
          <div className="deal-copy">
            <p className="eyebrow">Contract</p>
            <h2>{scenario.title}</h2>
            <p>{scenario.buyer}</p>
            <div className="rule-grid">
              {scenario.contractRules.map((rule) => (
                <span key={rule}>{rule}</span>
              ))}
            </div>
          </div>

          <div className="mode-panel">
            <p className="panel-title">Choose the outcome to demonstrate</p>
            <button className={delivery === 'good' ? 'choice active' : 'choice'} onClick={() => setDelivery('good')}>
              Successful delivery: seller gets paid
            </button>
            <button className={delivery === 'bad' ? 'choice active danger' : 'choice'} onClick={() => setDelivery('bad')}>
              Failed delivery: buyer is protected
            </button>
            <p className="delivery-text">{delivery === 'good' ? scenario.sellerGood : scenario.sellerBad}</p>
            <button className="run-button" onClick={() => runDemo(delivery)}>Run verification</button>
          </div>
        </section>

        <section className="outcome-cards" aria-label="Successful and failed outcomes">
          <button
            className={delivery === 'good' ? 'outcome-card success active' : 'outcome-card success'}
            onClick={() => runDemo('good')}
          >
            <span className="card-kicker">Demo A: Success</span>
            <strong>All checks pass, seller gets paid</strong>
            <p>DeliveryProof signs a release verdict. The payment rail can pay the seller.</p>
            <span className="card-action">Click to run success path</span>
          </button>
          <button
            className={delivery === 'bad' ? 'outcome-card danger active' : 'outcome-card danger'}
            onClick={() => runDemo('bad')}
          >
            <span className="card-kicker">Demo B: Failure</span>
            <strong>One check fails, buyer is protected</strong>
            <p>DeliveryProof catches the mismatch. The rail refunds or keeps the money on hold.</p>
            <span className="card-action">Click to run refund path</span>
          </button>
        </section>

        <section className="flow" aria-label="Verification flow">
          <FlowNode active={stage >= 1} title="1. Money held" text="Buyer payment is authorized or held by the rail." info="rail" />
          <Connector active={stage >= 2} />
          <FlowNode active={stage >= 2} title="2. Seller submits" text="The delivered output is bound to the contract nonce." info="proof" />
          <Connector active={stage >= 3} />
          <FlowNode active={stage >= 3} title="3. Checks run" text="DeliveryProof tests facts, not vibes." info="scope" />
          <Connector active={stage >= 6} />
          <FlowNode
            active={stage >= 6}
            title={passed ? '4. Release' : '4. Refund'}
            text={passed ? 'A signed receipt tells the rail to release.' : 'A signed receipt tells the rail not to pay.'}
            info="receipt"
            tone={passed ? 'success' : 'danger'}
          />
        </section>

        <section className="verification-zone">
          <div className="check-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Objective checks</p>
                <h3>What gets proven?</h3>
              </div>
              <Info term={scenarioKey === 'dataset' ? 'merkle' : 'proof'} />
            </div>
            <div className="checks">
              {checks.map(([name, ok, detail], index) => {
                const visible = visibleChecks.length > index;
                return (
                  <div key={name} className={visible ? 'check visible' : 'check'}>
                    <span className={ok ? 'status ok' : 'status fail'}>{ok ? 'pass' : 'fail'}</span>
                    <div>
                      <strong>{name}</strong>
                      <p>{detail}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <TerminalView lines={terminalLines} passed={passed} stage={stage} scenarioKey={scenarioKey} />
        </section>

        <PayloadPanel
          scenarioKey={scenarioKey}
          delivery={delivery}
          activeTab={payloadTab}
          onTabChange={setPayloadTab}
        />

        <SdkPanel scenarioKey={scenarioKey} passed={passed} />

        <SeamsPanel seamKey={seamKey} onSeamChange={setSeamKey} />
      </section>
    </main>
  );
}

function SeamsPanel({ seamKey, onSeamChange }) {
  const seam = seams[seamKey];
  return (
    <section className="seams-panel" aria-label="v0.9 production integration seams">
      <div className="seams-head">
        <div>
          <p className="eyebrow">v0.9 · production integration</p>
          <h2>Beyond the money-shot: the seams that make it safe to integrate</h2>
          <p>
            The money-shots above prove the protocol decides correctly. v0.9 adds the
            production wiring around it: key rotation, dispute bundles, Ethereum hash
            projection, and conformance suites third parties can self-certify against.
            These ship as a zero-deploy reference library — no real money moves here.
          </p>
        </div>
      </div>

      <div className="seams-tabs" role="tablist" aria-label="Production seams">
        {Object.entries(seams).map(([key, item]) => (
          <button
            key={key}
            role="tab"
            aria-selected={key === seamKey}
            className={key === seamKey ? 'seam-tab active' : 'seam-tab'}
            onClick={() => onSeamChange(key)}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="seams-body">
        <div className="seam-copy">
          <h3>
            {seam.title}
            <Info term={seam.info} />
          </h3>
          <p className="seam-summary">{seam.summary}</p>
          <ul className="seam-bullets">
            {seam.bullets.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
          <p className="seam-foot">{seam.foot}</p>
        </div>

        <div className="seam-terminal">
          <div className="terminal-header">
            <div>
              <p className="eyebrow">Under the hood</p>
              <h3>{seam.label} trace</h3>
            </div>
            <div className="terminal-lights" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
          </div>
          <pre className="terminal-screen" aria-label={`${seam.label} terminal trace`}>
            {seam.terminal.map((line) => line.text).join('\n')}
          </pre>
        </div>
      </div>
    </section>
  );
}

function buildTerminalLines({ scenarioKey, scenario, delivery, checks, passed, stage }) {
  const verifier = scenarioKey === 'dataset' ? 'dataset-merkle-sample' : scenarioKey;
  const visibleCheckCount = Math.max(0, Math.min(checks.length, stage - 2));
  const lines = [
    { kind: 'muted', text: '$ deliveryproof settle --rail stripe-or-x402 --verify objective' },
    { kind: 'info', text: 'rail.authorize(): buyer funds are held, not released yet' },
    { kind: 'json', text: `contract.intent = "${scenario.title}"` },
    { kind: 'json', text: `contract.verifier = "${verifier}"` },
  ];

  if (stage >= 2) {
    lines.push({
      kind: 'info',
      text: `seller.submit(): ${delivery === 'good' ? 'valid delivery received' : 'looks valid, but contains a hidden mismatch'}`,
    });
    lines.push({ kind: 'muted', text: 'evidence.outputHash = sha256(canonical(output))' });
  }

  if (stage >= 3) {
    lines.push({ kind: 'info', text: `verifier.run("${verifier}")` });
  }

  for (let i = 0; i < visibleCheckCount; i++) {
    const [name, ok, detail] = checks[i];
    lines.push({
      kind: ok ? 'ok' : 'fail',
      text: `${ok ? 'PASS' : 'FAIL'} ${name}: ${detail}`,
    });
  }

  if (stage >= 6) {
    lines.push({ kind: passed ? 'ok' : 'fail', text: `verdict.ok = ${passed}` });
    lines.push({ kind: passed ? 'ok' : 'fail', text: `receipt.decision = "${passed ? 'release' : 'refund'}"` });
    lines.push({ kind: 'info', text: 'receipt.signature = sign(canonical(receipt))' });
    lines.push({
      kind: passed ? 'ok' : 'fail',
      text: passed ? 'rail.capture(): seller gets paid' : 'rail.refund(): seller is not paid automatically',
    });
  }

  return lines;
}

function TerminalView({ lines, passed, stage, scenarioKey }) {
  const trace = lines.map((line, index) => `${index === 0 ? '' : '> '}${line.text}`).join('\n');
  return (
    <div className={stage >= 6 ? `terminal ${passed ? 'release' : 'refund'} show` : 'terminal'}>
      <div className="terminal-header">
        <div>
          <p className="eyebrow">Under the hood</p>
          <h3>Terminal view</h3>
        </div>
        <div className="terminal-lights" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </div>
      <pre className="terminal-screen" aria-label="DeliveryProof terminal trace">{trace}</pre>
      <div className="terminal-foot">
        {scenarioKey === 'dataset'
          ? 'Merkle sample mode proves selected rows are included and conform; it does not prove whole-dataset truth.'
          : 'The signed receipt is what a payment rail would use to release or refund.'}
      </div>
    </div>
  );
}

function PayloadPanel({ scenarioKey, delivery, activeTab, onTabChange }) {
  const payloads = buildPayloadExamples(scenarioKey, delivery);
  const tabs = [
    ['contract', 'Contract rules'],
    ['evidence', 'Seller evidence'],
    ['validation', 'Validation'],
  ];

  return (
    <section className="payload-panel" aria-label="Payload inspected">
      <div className="payload-head">
        <div>
          <p className="eyebrow">What gets sent?</p>
          <h2>Payload inspected</h2>
          <p>
            This is the concrete data DeliveryProof cares about: buyer rules,
            seller evidence, and deterministic checks. Values are shortened for readability.
          </p>
        </div>
        <div className="payload-tabs" role="tablist" aria-label="Payload tabs">
          {tabs.map(([key, label]) => (
            <button
              key={key}
              className={activeTab === key ? 'payload-tab active' : 'payload-tab'}
              onClick={() => onTabChange(key)}
              type="button"
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <pre className="payload-screen">{payloads[activeTab]}</pre>
    </section>
  );
}

function buildPayloadExamples(scenarioKey, delivery) {
  if (scenarioKey === 'dataset') {
    const row = delivery === 'good'
      ? `{ id: 43, region: 'eu', revenue: 120 }`
      : `{ id: 43, region: 'eu', revenue: -999 }`;
    return {
      contract: `predicate: {
  kind: 'dataset-merkle-sample',
  params: {
    merkleRoot: 'b62c...91af',
    rowCount: 1000,
    k: 5,
    columns: [
      { name: 'id', type: 'number', required: true },
      { name: 'region', type: 'string', domain: ['us','eu','apac'] },
      { name: 'revenue', type: 'number', range: { min: 0 } }
    ]
  }
}`,
      evidence: `evidence: {
  merkleSamples: [{
    index: 42,
    row: ${row},
    proof: {
      root: 'b62c...91af',
      leafCount: 1000,
      siblings: [
        { side: 'left', hash: '8ac1...02ee' },
        { side: 'right', hash: '4f09...c112' }
      ]
    }
  }]
}`,
      validation: `${delivery === 'good' ? '✓' : '✓'} selected index was derived from nonce + root + rowCount + k
${delivery === 'good' ? '✓' : '✓'} proof.root equals committed merkleRoot
${delivery === 'good' ? '✓' : '✓'} proof.leafCount equals committed rowCount
${delivery === 'good' ? '✓' : '✓'} row hash equals proof leaf
${delivery === 'good' ? '✓' : '✓'} Merkle proof verifies
${delivery === 'good' ? '✓' : '✕'} revenue satisfies range { min: 0 }

result: ${delivery === 'good' ? 'release' : 'refund'}`,
    };
  }

  if (scenarioKey === 'api') {
    const city = delivery === 'good' ? 'Amsterdam' : 'Rotterdam';
    return {
      contract: `predicate: {
  kind: 'api-response',
  params: {
    request: { method: 'GET', url: '/weather?city=Amsterdam' },
    status: 200,
    fields: [
      { path: '$.city', equals: 'Amsterdam' },
      { path: '$.temperature', type: 'number', min: -40, max: 60 }
    ],
    freshnessMs: 30000
  }
}`,
      evidence: `evidence.output: {
  contractId: 'contract_123',
  nonce: 'unique-contract-nonce',
  request: { method: 'GET', url: '/weather?city=Amsterdam' },
  response: {
    status: 200,
    body: { city: '${city}', temperature: 17 }
  }
}`,
      validation: `✓ status is 200
✓ JSON body has required fields
${delivery === 'good' ? '✓' : '✕'} $.city equals 'Amsterdam'
✓ response is bound to contractId + nonce

result: ${delivery === 'good' ? 'release' : 'refund'}`,
    };
  }

  return {
    contract: `predicate: {
  kind: 'document',
  params: {
    format: 'markdown',
    headings: [
      { text: 'Summary', level: 2 },
      { text: 'Risk', level: 2 }
    ],
    requiredTerms: ['refund policy'],
    checksums: [{ target: 'section', heading: 'Evidence', sha256: 'f8bd...aa10' }]
  }
}`,
    evidence: `evidence.output:
"""
# Delivery Report

## Summary
Work completed.

${delivery === 'good' ? '## Risk\\nNo open risk.\\n' : ''}
## Evidence
checksum-bound section...
"""`,
    validation: `✓ Markdown parses
${delivery === 'good' ? '✓' : '✕'} required heading "Risk" exists
✓ required term appears
${delivery === 'good' ? '✓' : '✕'} section checksum matches expected bytes

result: ${delivery === 'good' ? 'release' : 'refund'}`,
  };
}

function SdkPanel({ scenarioKey, passed }) {
  const verifierKind = scenarioKey === 'dataset' ? 'dataset-merkle-sample' : scenarioKey;
  const code = `import {
  settle,
  routeVerifier,
  createMockEscrowRail,
  generateKeypair
} from 'deliveryproof';

// 1. Define what "delivered" means.
const contract = {
  id: 'contract_123',
  deliverableType: '${verifierKind}',
  predicate: {
    kind: '${verifierKind}',
    params: {
      // objective rules: schema fields, API assertions,
      // document sections, Merkle root, etc.
    }
  },
  price: { amount: 25, currency: 'USDC' },
  nonce: 'unique-contract-nonce'
};

// 2. Route to the strongest verifier required by policy.
const route = routeVerifier(contract, {
  policy: { deliverableType: '${verifierKind}', minAssurance: 3 }
});

// 3. Run settlement. In production, replace the mock rail
// with a Stripe/x402 adapter.
const result = await settle({
  contract,
  verifier: route.verifier,
  routeDecision: route.routeDecision,
  rail: createMockEscrowRail(),
  settlementKey: generateKeypair(),
  produceEvidence: async () => sellerDeliveryEvidence
});

console.log(result.verdict.ok);        // ${passed ? 'true' : 'false'}
console.log(result.receipt.decision);  // '${passed ? 'release' : 'refund'}'`;

  return (
    <section className="sdk-panel" aria-label="SDK API usage">
      <div className="sdk-copy">
        <p className="eyebrow">SDK / API usage</p>
        <h2>How someone actually calls DeliveryProof</h2>
        <p>
          DeliveryProof is currently a JavaScript SDK/library, not a hosted REST API.
          Your app creates the contract, routes it to a verifier, calls `settle()`,
          and receives a signed receipt with a release or refund decision.
        </p>
      </div>
      <pre className="code-screen">{code}</pre>
    </section>
  );
}

function FlowNode({ active, title, text, info, tone = 'neutral' }) {
  return (
    <div className={`flow-node ${active ? 'active' : ''} ${tone}`}>
      <div className="node-dot" />
      <h3>{title} <Info term={info} /></h3>
      <p>{text}</p>
    </div>
  );
}

function Connector({ active }) {
  return <div className={active ? 'connector active' : 'connector'} />;
}

function Info({ term }) {
  return (
    <span className="info" tabIndex="0" aria-label={glossary[term]}>
      i
      <span className="tooltip">{glossary[term]}</span>
    </span>
  );
}

createRoot(document.getElementById('root')).render(<App />);
