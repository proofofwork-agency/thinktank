import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = process.env.DELIVERYPROOF_DEP_GUARD_ROOT ?? process.cwd();
const ALLOWED_RUNTIME_DEPS = Object.freeze({ '@noble/hashes': '2.2.0' });
const EMPTY_BUCKETS = Object.freeze(['devDependencies', 'peerDependencies', 'optionalDependencies']);

const pkg = readJson('package.json');
const lock = readJson('package-lock.json');

assertExactObject(pkg.dependencies ?? {}, ALLOWED_RUNTIME_DEPS, 'package.json dependencies');
for (const bucket of EMPTY_BUCKETS) {
  assertExactObject(pkg[bucket] ?? {}, {}, `package.json ${bucket}`);
}

if (lock.lockfileVersion !== 3) {
  throw new Error(`package-lock.json lockfileVersion must be 3, got ${lock.lockfileVersion}`);
}
if (!lock.packages || typeof lock.packages !== 'object' || Array.isArray(lock.packages)) {
  throw new Error('package-lock.json packages map is required');
}

const packageEntries = Object.keys(lock.packages).sort();
assertExactArray(packageEntries, ['', 'node_modules/@noble/hashes'], 'package-lock package entries');

const root = lock.packages[''];
if (!root || typeof root !== 'object') throw new Error('package-lock root package entry is required');
if (root.name !== pkg.name) throw new Error('package-lock root name drift');
if (root.version !== pkg.version) throw new Error('package-lock root version drift');
assertExactObject(root.dependencies ?? {}, ALLOWED_RUNTIME_DEPS, 'package-lock root dependencies');

const noble = lock.packages['node_modules/@noble/hashes'];
if (!noble || typeof noble !== 'object') throw new Error('package-lock @noble/hashes entry is required');
if (noble.version !== ALLOWED_RUNTIME_DEPS['@noble/hashes']) {
  throw new Error(`@noble/hashes lock version must be ${ALLOWED_RUNTIME_DEPS['@noble/hashes']}`);
}
for (const bucket of ['dependencies', 'optionalDependencies', 'peerDependencies']) {
  assertExactObject(noble[bucket] ?? {}, {}, `@noble/hashes ${bucket}`);
}

function readJson(file) {
  try {
    return JSON.parse(readFileSync(join(ROOT, file), 'utf8'));
  } catch (err) {
    throw new Error(`${file} is required and must be valid JSON: ${err.message}`);
  }
}

function assertExactObject(actual, expected, label) {
  if (!actual || typeof actual !== 'object' || Array.isArray(actual)) {
    throw new Error(`${label} must be an object`);
  }
  const actualEntries = Object.entries(actual).sort(([a], [b]) => a.localeCompare(b));
  const expectedEntries = Object.entries(expected).sort(([a], [b]) => a.localeCompare(b));
  assertExactArray(
    actualEntries.map(([name, version]) => `${name}@${version}`),
    expectedEntries.map(([name, version]) => `${name}@${version}`),
    label,
  );
}

function assertExactArray(actual, expected, label) {
  if (actual.length !== expected.length || actual.some((value, index) => value !== expected[index])) {
    throw new Error(`${label} must be exactly [${expected.join(', ')}], got [${actual.join(', ')}]`);
  }
}
