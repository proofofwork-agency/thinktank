import { parentPort, workerData } from 'node:worker_threads';
import { replayBuiltinReplayTask } from './builtin-replay-core.mjs';

if (!parentPort) {
  throw new Error('builtin-replay-worker must run inside a worker thread');
}

parentPort.postMessage(replayBuiltinReplayTask(workerData));
