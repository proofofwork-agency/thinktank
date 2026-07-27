// replay-transitions.mjs — the replay-key state machine, shared by every store.
//
// A leaf module (imports nothing) so the WAL store, the SQLite store, and any
// third-party store can enforce identical semantics.
//
// WHY THIS EXISTS
//
// `mark(key, state, at)` authenticates nothing but the key: it cannot tell the
// settlement that reserved a nonce from any other caller that knows the same
// deterministic key. Adversarial review used that to advance another party's row
// and then REGRESS it (`reserved -> captured -> reserved`), and to reserve a key
// directly into a terminal state — defeating the interface's claim that a state
// was advanced by the settlement that reserved it.
//
// The signature is fixed by the ReplayStore conformance contract, so a
// capability token is not available to us. What IS available is making the
// transitions themselves monotonic: a reservation starts at `reserved`, moves
// once to a terminal, and never moves again. That does not authenticate the
// caller, but it removes every transition an attacker would actually want:
// no regression, no terminal flip, no reserving straight into a terminal.
//
// The residual risk is honest and documented: a caller who knows the key can
// still drive the FIRST reserved -> terminal transition. Authenticating that
// requires a token the interface has no room for.

/** The only state a reservation may be created in. */
export const INITIAL_REPLAY_STATE = 'reserved';

/** States a reservation may finish in. Terminal: no transition leaves them. */
export const TERMINAL_REPLAY_STATES = Object.freeze(['captured', 'refunded']);

/**
 * Validate the state a reservation is being created in.
 *
 * @param {string} state
 * @throws {Error} if the caller tries to reserve straight into a terminal state
 */
export function assertReservableState(state) {
  if (state !== INITIAL_REPLAY_STATE) {
    throw new Error(
      `replay store reserve must create state '${INITIAL_REPLAY_STATE}', got '${state}' — ` +
        'a reservation cannot be created already settled',
    );
  }
}

/**
 * Validate a state transition on an existing reservation.
 *
 * Allowed:
 *   reserved -> captured
 *   reserved -> refunded
 *   captured -> captured   (idempotent retry of the same terminal)
 *   refunded -> refunded   (idempotent retry of the same terminal)
 *
 * Everything else — regression to `reserved`, flipping one terminal to the
 * other, or inventing a state — is rejected.
 *
 * @param {string} from current stored state
 * @param {string} to requested state
 * @param {string} key for the error message
 * @throws {Error} on an illegal transition
 */
export function assertReplayTransition(from, to, key) {
  if (!TERMINAL_REPLAY_STATES.includes(to)) {
    throw new Error(
      `replay store mark for key ${key}: state must be one of ${TERMINAL_REPLAY_STATES.join('|')}, got '${to}'`,
    );
  }
  if (from === to) return; // idempotent retry of the same terminal
  if (from !== INITIAL_REPLAY_STATE) {
    throw new Error(
      `replay store mark for key ${key}: '${from}' is terminal and cannot become '${to}'`,
    );
  }
}
