import { readdir, readFile } from "node:fs/promises";
import { join, relative } from "node:path";

const root = new URL("..", import.meta.url).pathname;
const forbidden = [["ha", "ddo"].join(""), ["@", "ha", "ddo"].join(""), ["agent", "os"].join("")];
const self = new URL(import.meta.url).pathname;
const ignored = new Set(["node_modules", "dist", ".git", "coverage", "package-lock.json"]);

async function walk(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (ignored.has(entry.name)) continue;
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await walk(full)));
    } else if (/\.(ts|js|json|md|mjs|txt)$/.test(entry.name)) {
      files.push(full);
    }
  }
  return files;
}

const hits = [];
for (const file of await walk(root)) {
  if (file === self) continue;
  const text = await readFile(file, "utf8");
  for (const term of forbidden) {
    if (text.toLowerCase().includes(term)) {
      hits.push(`${relative(root, file)} contains ${term}`);
    }
  }
}

if (hits.length > 0) {
  console.error(hits.join("\n"));
  process.exit(1);
}
