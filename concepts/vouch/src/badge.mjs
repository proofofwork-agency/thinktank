// The badge — how vouch distributes itself.
//
// The distribution strategy is not marketing, it is the mechanism. An agent
// that has been vouched holds something buyers want to see, so it displays it;
// displaying it advertises vouch to every buyer who reads the listing; buyers
// start expecting a score; agents without one start seeking cover. The loop is
// the same one that made TLS padlocks and "Powered by Stripe" ubiquitous, with
// one difference: this badge cannot be self-awarded, because the number in it
// is derived from capital that was actually put at risk and outcomes that were
// actually settled.
//
// A badge is therefore a *claim*, not a credential. It carries the ledger head
// it was derived from, so any reader can replay the ledger and recompute it.
// Faking one is not forgery-resistant by obscurity; it is pointless, because
// verification is a pure function anybody can run.

import { domainDigest } from './canonical.mjs';
import { replayOracle } from './oracle.mjs';

/**
 * Mint a badge for an agent from a ledger.
 * The badge is fully determined by (ledger, agent) — there is no signing key
 * and no issuer, which is what keeps it permissionless.
 */
export function mintBadge(ledger, agent, { exposure = 1_000_000 } = {}) {
  const oracle = replayOracle(ledger);
  const { delivered, failed } = oracle.history(agent);
  const body = {
    agent,
    scoreBasisPoints: oracle.scoreBasisPoints(agent),
    delivered,
    failed,
    referencePremium: oracle.fairPremium(agent, exposure),
    referenceExposure: exposure,
    ledgerHead: ledger.head,
    ledgerLength: ledger.length,
  };
  return Object.freeze({ ...body, badgeId: domainDigest('badge', body) });
}

/**
 * Verify a badge against a ledger by recomputing it. Returns the mismatch
 * rather than just a boolean, so a buyer can see *how* a claim was inflated.
 */
export function verifyBadge(ledger, badge) {
  const recomputed = mintBadge(ledger, badge.agent, { exposure: badge.referenceExposure });

  // Check the badge against itself first. Editing a displayed field while
  // keeping the original badgeId is the cheapest forgery available, and
  // comparing ids alone would wave it straight through.
  const selfDigest = domainDigest('badge', {
    agent: badge.agent,
    scoreBasisPoints: badge.scoreBasisPoints,
    delivered: badge.delivered,
    failed: badge.failed,
    referencePremium: badge.referencePremium,
    referenceExposure: badge.referenceExposure,
    ledgerHead: badge.ledgerHead,
    ledgerLength: badge.ledgerLength,
  });
  if (selfDigest !== badge.badgeId) {
    return {
      valid: false,
      reason: 'badge contents do not hash to its own badgeId',
      claimed: badge.scoreBasisPoints,
      actual: recomputed.scoreBasisPoints,
    };
  }

  if (ledger.head !== badge.ledgerHead) {
    return {
      valid: false,
      reason: 'badge was minted against a different ledger state',
      claimed: badge.scoreBasisPoints,
      actual: recomputed.scoreBasisPoints,
    };
  }

  if (recomputed.badgeId !== badge.badgeId) {
    return {
      valid: false,
      reason: 'badge contents do not match the ledger',
      claimed: badge.scoreBasisPoints,
      actual: recomputed.scoreBasisPoints,
    };
  }

  return { valid: true, reason: 'badge matches the ledger' };
}

const TIERS = [
  { min: 9_500, label: 'vouched', color: '#0f9d58' },
  { min: 8_500, label: 'covered', color: '#7cb342' },
  { min: 6_000, label: 'thin', color: '#f9a825' },
  { min: 0, label: 'unproven', color: '#9e9e9e' },
];

export function tierOf(scoreBasisPoints) {
  return TIERS.find((tier) => scoreBasisPoints >= tier.min) ?? TIERS.at(-1);
}

/** Human-readable percentage, e.g. 9432 -> "94.3%". */
export function formatScore(scoreBasisPoints) {
  return `${(scoreBasisPoints / 100).toFixed(1)}%`;
}

/**
 * Self-contained SVG. No external fetch, no CDN, no tracking — an agent can
 * paste it into a README, an MCP manifest, or a listing page and it renders
 * everywhere.
 */
export function renderBadgeSVG(badge) {
  const tier = tierOf(badge.scoreBasisPoints);
  const value = `${formatScore(badge.scoreBasisPoints)} ${tier.label}`;
  const labelText = 'vouched';
  const labelWidth = 58;
  const valueWidth = 8 + value.length * 6.6;
  const total = labelWidth + valueWidth;

  return [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${total.toFixed(0)}" height="20" role="img" aria-label="${labelText}: ${value}">`,
    `<title>${labelText}: ${value}</title>`,
    `<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>`,
    `<clipPath id="r"><rect width="${total.toFixed(0)}" height="20" rx="3" fill="#fff"/></clipPath>`,
    `<g clip-path="url(#r)">`,
    `<rect width="${labelWidth}" height="20" fill="#555"/>`,
    `<rect x="${labelWidth}" width="${valueWidth.toFixed(0)}" height="20" fill="${tier.color}"/>`,
    `<rect width="${total.toFixed(0)}" height="20" fill="url(#s)"/>`,
    `</g>`,
    `<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">`,
    `<text x="${(labelWidth / 2).toFixed(0)}" y="14">${labelText}</text>`,
    `<text x="${(labelWidth + valueWidth / 2).toFixed(0)}" y="14">${value}</text>`,
    `</g>`,
    `</svg>`,
  ].join('');
}

/** Markdown an agent drops straight into its README. */
/** Cost of cover as a rate, so the badge is readable without knowing the unit. */
export function premiumRateBasisPoints(badge) {
  if (badge.referenceExposure === 0) return 0;
  return Math.round((badge.referencePremium / badge.referenceExposure) * 10_000);
}

export function renderBadgeMarkdown(badge) {
  const tier = tierOf(badge.scoreBasisPoints);
  return [
    `**vouched ${formatScore(badge.scoreBasisPoints)}** (${tier.label}) — `,
    `${badge.delivered} delivered / ${badge.failed} failed · `,
    `cover costs ${premiumRateBasisPoints(badge)} bps · `,
    `verify against ledger \`${badge.ledgerHead.slice(0, 12)}…\``,
  ].join('');
}

/**
 * A fragment an agent merges into its MCP server manifest. MCP is the
 * distribution surface: it is where 2026's agents already advertise
 * themselves, so a score that lives there is seen at the moment of hiring.
 */
export function renderMCPFragment(badge) {
  return {
    'x-vouch': {
      agent: badge.agent,
      score: badge.scoreBasisPoints,
      tier: tierOf(badge.scoreBasisPoints).label,
      delivered: badge.delivered,
      failed: badge.failed,
      ledgerHead: badge.ledgerHead,
      badgeId: badge.badgeId,
    },
  };
}
