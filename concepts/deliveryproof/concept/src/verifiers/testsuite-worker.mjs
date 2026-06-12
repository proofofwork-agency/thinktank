import { parentPort, workerData } from 'node:worker_threads';
import { replayTestsuiteTask } from './testsuite-core.mjs';

if (!parentPort) {
  throw new Error('testsuite-worker must run inside a worker thread');
}

parentPort.postMessage(replayTestsuiteTask(workerData));
