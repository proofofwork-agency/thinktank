import { ToolLoopAgent, stepCountIs, tool } from "ai";
import { z } from "zod";

export const INSTRUCTIONS =
  "Resolve refund requests. If the user provides an order ID, call lookupOrder with that ID before answering. Never refund expired orders.";

export const INPUT = "Can order ID 123 be refunded? Use lookupOrder to check order 123 first.";

export const lookupOrder = tool({
  description: "Look up an order by ID.",
  inputSchema: z.object({ orderId: z.string() }),
  execute: async ({ orderId }) => ({
    orderId,
    status: orderId === "123" ? "expired" : "open",
    refundable: orderId !== "123",
    amount: orderId === "123" ? 49.99 : 12.5,
  }),
});

/**
 * The agent factory used by production, recording, and replay alike —
 * only the model differs. This is the pattern Actweave is built around.
 */
export function buildSupportAgent(model, { instructions = INSTRUCTIONS, tools = { lookupOrder } } = {}) {
  return new ToolLoopAgent({
    model,
    instructions,
    tools,
    stopWhen: stepCountIs(5),
  });
}
