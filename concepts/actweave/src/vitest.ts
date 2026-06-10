import { check, resolveCheckSource, type CheckSource, type MatchGoldenOptions } from "./check/index.js";
import { assertReplayable, type AssertReplayableOptions, type ReplayFixtureSource } from "./replay/index.js";

type MatcherResult = { pass: boolean; message: () => string };

function run(assertion: () => void, pass: string): MatcherResult {
  try {
    assertion();
    return { pass: true, message: () => pass };
  } catch (error) {
    return { pass: false, message: () => (error instanceof Error ? error.message : String(error)) };
  }
}

export const actweaveMatchers = {
  toBeCompletedRun(received: CheckSource): MatcherResult {
    return run(() => check(received).completed(), "expected run not to be completed");
  },
  toHaveCalledTool(received: CheckSource, toolName: string, input?: unknown): MatcherResult {
    return run(() => {
      const checker = check(received).called(toolName);
      if (input !== undefined) {
        checker.calledWith(toolName, input);
      }
    }, `expected tool "${toolName}" not to be called`);
  },
  toHaveEventSequence(received: CheckSource, types: readonly string[]): MatcherResult {
    return run(() => check(received).eventSequence(types), "expected event sequence not to match");
  },
  toHaveNoErrors(received: CheckSource): MatcherResult {
    return run(() => check(received).noErrors(), "expected errors in the run");
  },
  toHaveValidLifecycle(received: CheckSource): MatcherResult {
    return run(() => check(received).validLifecycle(), "expected an invalid lifecycle");
  },
  toHaveEnforcedPolicy(received: CheckSource, code?: string): MatcherResult {
    return run(() => check(received).policyEnforced(code), "expected no policy enforcement events");
  },
  toMatchGolden(received: CheckSource, path: string, options?: MatchGoldenOptions): MatcherResult {
    return run(() => check(received).toMatchGolden(path, options), `expected run not to match golden ${path}`);
  },
  async toBeReplayable(received: ReplayFixtureSource, options: AssertReplayableOptions): Promise<MatcherResult> {
    try {
      await assertReplayable(received, options);
      return { pass: true, message: () => "expected fixture not to be replayable" };
    } catch (error) {
      return { pass: false, message: () => (error instanceof Error ? error.message : String(error)) };
    }
  },
};

export interface ActweaveMatchers<R = unknown> {
  toBeCompletedRun(): R;
  toHaveCalledTool(toolName: string, input?: unknown): R;
  toHaveEventSequence(types: readonly string[]): R;
  toHaveNoErrors(): R;
  toHaveValidLifecycle(): R;
  toHaveEnforcedPolicy(code?: string): R;
  toMatchGolden(path: string, options?: MatchGoldenOptions): R;
  toBeReplayable(options: AssertReplayableOptions): Promise<R>;
}

type ExpectLike = { extend(matchers: Record<string, unknown>): void };

export function extendActweaveMatchers(expect: ExpectLike): void {
  expect.extend(actweaveMatchers);
}

export { resolveCheckSource };
