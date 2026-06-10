import { isRecord } from "../internal/guards.js";
import type { LedgerRecorder, RecorderToolRisk } from "./recorder.js";

export type RecordToolsOptions = {
  /** Risk level per tool name; defaults to "unknown" (treated as side-effectful in replay checks). */
  risk?: Record<string, RecorderToolRisk>;
};

type ToolExecuteOptions = {
  toolCallId?: string;
  [key: string]: unknown;
};

/**
 * Wrap an AI SDK tool set so every execute() is recorded as
 * tool.called/tool.completed/tool.failed, correlated by the SDK's toolCallId
 * (parallel tool calls in one step stay distinct). Tools without execute
 * (client-side or approval-deferred) pass through untouched; all other tool
 * properties (description, inputSchema, needsApproval, outputSchema, hooks)
 * are preserved.
 */
export function recordTools<TTools extends Record<string, unknown>>(
  tools: TTools,
  recorder: LedgerRecorder,
  options: RecordToolsOptions = {},
): TTools {
  const wrapped: Record<string, unknown> = {};
  for (const [name, tool] of Object.entries(tools)) {
    wrapped[name] = wrapTool(name, tool, recorder, options.risk?.[name] ?? "unknown");
  }
  return wrapped as TTools;
}

function wrapTool(name: string, tool: unknown, recorder: LedgerRecorder, risk: RecorderToolRisk): unknown {
  if (!isRecord(tool) || typeof tool.execute !== "function") {
    return tool;
  }
  const execute = tool.execute as (input: unknown, execOptions?: ToolExecuteOptions) => unknown;
  return {
    ...tool,
    execute: async (input: unknown, execOptions?: ToolExecuteOptions) => {
      const step = recorder.currentStep();
      const callId = typeof execOptions?.toolCallId === "string" ? execOptions.toolCallId : undefined;
      await recorder.toolCalled(step, name, input, risk, undefined, callId);
      try {
        const output = await execute(input, execOptions);
        await recorder.toolCompleted(step, name, output, undefined, callId);
        return output;
      } catch (error) {
        await recorder.toolFailed(step, name, error, undefined, callId);
        throw error;
      }
    },
  };
}
