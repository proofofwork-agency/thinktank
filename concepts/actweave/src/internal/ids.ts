import { randomUUID } from "node:crypto";

export function createId(prefix: string): string {
  const random = Math.random().toString(36).slice(2, 8);
  const uuid = randomUUID().slice(0, 8);
  return `${prefix}_${Date.now().toString(36)}_${uuid}_${random}`;
}
