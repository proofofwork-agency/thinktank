import type { LanguageModelV3 } from "@ai-sdk/provider";
import { isRecord } from "../internal/guards.js";
import { recordModel } from "../record/model.js";
import type { LedgerRecorder } from "../record/recorder.js";
import { loadReplayFixture, type ReplayFixture, type ReplayFixtureSource } from "./fixture.js";
import { replayModel, type ReplayLanguageModel, type ReplayMode } from "./model.js";
import type { RequestDrift } from "./diff.js";
import { compareRuns, type CompareRunsOptions } from "./compare.js";

export type ReplayableAgent = {
  generate(options: { prompt: string }): Promise<unknown>;
};

export type AssertReplayableOptions = {
  /** Build your real agent around the replay model — same construction as production, different model. */
  agent: (model: ReplayLanguageModel) => ReplayableAgent | Promise<ReplayableAgent>;
  /** Run input. Defaults to the fixture's recorded run.started input. */
  input?: string;
  mode?: ReplayMode;
  hashSettings?: boolean;
  /** Compare the agent's final text against the fixture's recorded output (default true). */
  compareOutput?: boolean;
  /**
   * Optional recorder for full event-level comparison: pass a recorder and
   * wrap your tools with recordTools(tools, recorder); the replayed run's
   * ledger is then compared to the fixture with compareRuns().
   */
  recorder?: LedgerRecorder;
  compare?: CompareRunsOptions;
};

export type AssertReplayableResult = {
  fixture: ReplayFixture;
  result: unknown;
  text?: string;
  drift: RequestDrift[];
};

/**
 * The one-liner CI test: replay a recorded fixture through your real agent
 * with no API key. Strict mode (default) fails with a drift diff when the
 * prompt, tools, or tool results diverge from the recording; exhaustion
 * checks fail when the loop grew or shrank a step.
 */
export async function assertReplayable(
  source: ReplayFixtureSource,
  options: AssertReplayableOptions,
): Promise<AssertReplayableResult> {
  const fixture = await loadReplayFixture(source);
  const replay = replayModel(fixture, { mode: options.mode, hashSettings: options.hashSettings });

  const model: LanguageModelV3 = options.recorder ? recordModel(replay, options.recorder) : replay;
  const agent = await options.agent(attachReplayApi(model, replay));

  const input = options.input ?? (typeof fixture.input === "string" ? fixture.input : undefined);
  if (input === undefined) {
    throw new Error(
      "assertReplayable: no input available — the fixture has no recorded run.started input; pass options.input",
    );
  }

  const result = await agent.generate({ prompt: input });
  replay.assertExhausted();

  const text = extractText(result);
  if (options.compareOutput !== false) {
    const expected = expectedFinalText(fixture);
    if (expected !== undefined && text !== undefined && text !== expected) {
      throw new Error(
        [
          "Replay output differs from the recorded output:",
          `  recorded: ${JSON.stringify(expected)}`,
          `  actual:   ${JSON.stringify(text)}`,
          "The replayed model responses are fixed, so this indicates the agent assembled the final output differently (loop, output processing, or version change).",
        ].join("\n"),
      );
    }
  }

  if (options.recorder && options.compare) {
    const diff = compareRuns(fixture.events, [...options.recorder.events()], options.compare);
    if (!diff.pass) {
      throw new Error(`Replay event comparison failed:\n${diff.issues.map((issue) => `  - ${issue}`).join("\n")}`);
    }
  }

  return { fixture, result, text, drift: replay.driftReport() };
}

/** Keep the replay inspection API visible on the (possibly record-wrapped) model handed to the factory. */
function attachReplayApi(model: LanguageModelV3, replay: ReplayLanguageModel): ReplayLanguageModel {
  if (model === replay) {
    return replay;
  }
  return Object.assign(Object.create(Object.getPrototypeOf(model) as object | null) as object, model, {
    actweaveReplay: true as const,
    remaining: () => replay.remaining(),
    driftReport: () => replay.driftReport(),
    assertExhausted: () => replay.assertExhausted(),
  }) as ReplayLanguageModel;
}

function extractText(result: unknown): string | undefined {
  return isRecord(result) && typeof result.text === "string" ? result.text : undefined;
}

function expectedFinalText(fixture: ReplayFixture): string | undefined {
  if (typeof fixture.runOutput === "string") {
    return fixture.runOutput;
  }
  const lastResponse = fixture.modelCalls.at(-1)?.response;
  if (lastResponse && Array.isArray(lastResponse.content)) {
    const text = lastResponse.content
      .filter(
        (part): part is { type: "text"; text: string } =>
          isRecord(part) && part.type === "text" && typeof part.text === "string",
      )
      .map((part) => part.text)
      .join("");
    return text.length > 0 ? text : undefined;
  }
  return undefined;
}
