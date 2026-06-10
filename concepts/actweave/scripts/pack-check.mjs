// Verifies the publishable package: tarball contents stay lean and every
// exports-map entry points at a real, importable build artifact.
// Run after `npm run build`.

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
const failures = [];

// 1. Tarball contents: only dist + docs essentials.
const packOutput = JSON.parse(execFileSync("npm", ["pack", "--dry-run", "--json"], { encoding: "utf8" }));
const files = packOutput[0].files.map((file) => file.path);
const allowed = /^(dist\/|README\.md$|LICENSE$|CHANGELOG\.md$|package\.json$)/;
for (const file of files) {
  if (!allowed.test(file)) {
    failures.push(`unexpected file in package: ${file}`);
  }
}
if (!files.some((file) => file.startsWith("dist/"))) {
  failures.push("package contains no dist/ output — run npm run build first");
}

// 2. Every subpath export resolves and imports.
for (const [subpath, entry] of Object.entries(pkg.exports)) {
  if (subpath === "./package.json") {
    continue;
  }
  const target = typeof entry === "string" ? entry : entry.import;
  if (!existsSync(new URL(`../${target}`, import.meta.url))) {
    failures.push(`exports["${subpath}"] points at missing file ${target}`);
    continue;
  }
  try {
    await import(pathToFileURL(new URL(`../${target}`, import.meta.url).pathname).href);
  } catch (error) {
    failures.push(`exports["${subpath}"] failed to import: ${error.message}`);
  }
  const types = typeof entry === "object" ? entry.types : undefined;
  if (types && !existsSync(new URL(`../${types}`, import.meta.url))) {
    failures.push(`exports["${subpath}"] types point at missing file ${types}`);
  }
}

if (failures.length > 0) {
  console.error(`pack-check failed:\n${failures.map((failure) => `  - ${failure}`).join("\n")}`);
  process.exit(1);
}
console.log(
  `pack-check passed: ${files.length} files, ${Object.keys(pkg.exports).length - 1} subpath exports importable.`,
);
