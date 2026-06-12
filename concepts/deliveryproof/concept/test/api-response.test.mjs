// test/api-response.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';

import { apiResponseVerifier } from '../src/verifiers/api-response.mjs';
import { getVerifier, verifiers } from '../src/verifiers/index.mjs';
import { routeVerifier } from '../src/router/policy.mjs';

// A weather-API contract: buyer asked for Amsterdam, max price 5, fresh within 60s.
function weatherContract(extraParams = {}) {
  return {
    id: 'c_api_1',
    nonce: 'n_api_1',
    deliverableType: 'api-response',
    createdAt: 1_000_000,
    predicate: {
      kind: 'api-response',
      params: {
        request: { method: 'GET', url: 'https://api.example.com/weather?city=Amsterdam' },
        status: { min: 200, max: 299 },
        contentType: 'application/json',
        fields: [
          { path: 'city', equals: 'Amsterdam' },
          { path: 'temperature', type: 'number', min: -90, max: 60 },
          { path: 'price', max: 5 },
        ],
        freshnessMs: 60_000,
        ...extraParams,
      },
    },
  };
}

function transcript(body, { status = 200, producedAt = 1_000_000, ct = 'application/json', url = 'https://api.example.com/weather?city=Amsterdam', contractId = 'c_api_1', nonce = 'n_api_1' } = {}) {
  return {
    output: {
      contractId,
      nonce,
      request: { method: 'GET', url },
      response: { status, headers: { 'Content-Type': ct }, body },
      producedAt,
    },
  };
}

const goodBody = { city: 'Amsterdam', temperature: 21, price: 3 };

test('api-response: registered in registry and router profile (tier 3, api-response)', () => {
  assert.equal(getVerifier('api-response'), apiResponseVerifier);
  assert.equal(verifiers['api-response'], apiResponseVerifier);
  const { verifier, routeDecision } = routeVerifier(weatherContract(), {
    policy: { deliverableType: 'api-response', minAssurance: 3 },
  });
  assert.equal(routeDecision.selected, 'api-response');
  assert.equal(verifier, apiResponseVerifier);
});

test('api-response: passes a correct response', () => {
  const v = apiResponseVerifier.verify(weatherContract(), transcript(goodBody));
  assert.equal(v.ok, true);
  assert.equal(v.tier, 'A');
  assert.equal(v.verifier, 'api-response');
});

test('api-response: MONEY-SHOT — schema-valid but wrong city refunds (shape would pass)', () => {
  // Right shape (string city, number temp/price), wrong entity: London, not Amsterdam.
  const wrong = { city: 'London', temperature: 21, price: 3 };
  // The shallow schema verifier (shape only) would PASS this:
  const shape = getVerifier('schema').verify(
    { predicate: { kind: 'schema', params: { schema: { type: 'object',
      properties: { city: { type: 'string' }, temperature: { type: 'number' }, price: { type: 'number' } },
      required: ['city', 'temperature', 'price'] } } } },
    { output: wrong },
  );
  assert.equal(shape.ok, true, 'shallow schema must accept the wrong-but-valid response');
  // The deep api-response verifier must REJECT it:
  const v = apiResponseVerifier.verify(weatherContract(), transcript(wrong));
  assert.equal(v.ok, false);
  assert.match(v.reason, /city/);
  assert.equal(v.diff.field, 'city');
});

test('api-response: fails on price over the agreed max', () => {
  const v = apiResponseVerifier.verify(weatherContract(), transcript({ city: 'Amsterdam', temperature: 21, price: 9 }));
  assert.equal(v.ok, false);
  assert.match(v.reason, /price/);
});

test('api-response: fails on a stale response (freshness window)', () => {
  const v = apiResponseVerifier.verify(weatherContract(), transcript(goodBody, { producedAt: 2_000_000 }));
  assert.equal(v.ok, false);
  assert.match(v.reason, /stale/);
});

test('api-response: fails on non-2xx status', () => {
  const v = apiResponseVerifier.verify(weatherContract(), transcript(goodBody, { status: 500 }));
  assert.equal(v.ok, false);
  assert.match(v.reason, /status/);
});

test('api-response: fails on content-type mismatch', () => {
  const v = apiResponseVerifier.verify(weatherContract(), transcript(goodBody, { ct: 'text/html' }));
  assert.equal(v.ok, false);
  assert.match(v.reason, /content-type/);
});

test('api-response: fails on request-binding mismatch (different URL than contracted)', () => {
  const v = apiResponseVerifier.verify(weatherContract(), transcript(goodBody, { url: 'https://api.example.com/weather?city=Berlin' }));
  assert.equal(v.ok, false);
  assert.match(v.reason, /request\.url/);
});

test('api-response: fromRequest binds response value to request value', () => {
  const contract = {
    id: 'c', nonce: 'n', deliverableType: 'api-response', createdAt: 0,
    predicate: { kind: 'api-response', params: {
      fields: [{ path: 'echo.city', fromRequest: 'query.city' }],
    } },
  };
  const ok = apiResponseVerifier.verify(contract, {
    output: { contractId: 'c', nonce: 'n', request: { method: 'GET', url: 'u', query: { city: 'Paris' } },
      response: { status: 200, body: { echo: { city: 'Paris' } } } },
  });
  assert.equal(ok.ok, true);
  const bad = apiResponseVerifier.verify(contract, {
    output: { contractId: 'c', nonce: 'n', request: { method: 'GET', url: 'u', query: { city: 'Paris' } },
      response: { status: 200, body: { echo: { city: 'Rome' } } } },
  });
  assert.equal(bad.ok, false);
  assert.match(bad.reason, /does not match request/);
});

test('api-response: BINDING — rejects a transcript from a different contract (replay guard)', () => {
  // A perfectly valid response, but captured under a DIFFERENT contractId -> must reject.
  const v = apiResponseVerifier.verify(weatherContract(), transcript(goodBody, { contractId: 'c_OTHER' }));
  assert.equal(v.ok, false);
  assert.match(v.reason, /contractId/);
  assert.equal(v.diff.reason, 'contract binding mismatch');
});

test('api-response: BINDING — rejects a transcript with a mismatched nonce (replay guard)', () => {
  const v = apiResponseVerifier.verify(weatherContract(), transcript(goodBody, { nonce: 'n_OTHER' }));
  assert.equal(v.ok, false);
  assert.match(v.reason, /nonce/);
  assert.match(v.diff.reason, /replay/);
});

test('api-response: BINDING — requires a request object in the transcript', () => {
  const v = apiResponseVerifier.verify(weatherContract(), {
    output: { contractId: 'c_api_1', nonce: 'n_api_1', response: { status: 200, headers: { 'Content-Type': 'application/json' }, body: goodBody } },
  });
  assert.equal(v.ok, false);
  assert.match(v.reason, /missing a request/);
});

test('api-response: rejects a malformed transcript', () => {
  const v = apiResponseVerifier.verify(weatherContract(), { output: [1, 2, 3] });
  assert.equal(v.ok, false);
  assert.match(v.reason, /transcript/);
});

test('router: does NOT silently downgrade api-response to schema at minAssurance 3', () => {
  // With maxCost too low to admit a tier-3 verifier and fallback off, it must throw.
  assert.throws(
    () => routeVerifier(weatherContract(), { policy: { deliverableType: 'api-response', minAssurance: 3, maxCost: 1 } }),
    /no verifier meets required assurance/,
  );
});
