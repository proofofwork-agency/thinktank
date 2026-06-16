"""Parse pytest ``-rA`` short-test-summary output."""

SUMMARY_HEADER = "short test summary info"
PASS_STATUSES = {"PASSED", "XPASS"}
FAIL_STATUSES = {"FAILED", "ERROR"}
IGNORE_STATUSES = {"SKIPPED", "XFAIL"}
ALL_STATUSES = PASS_STATUSES | FAIL_STATUSES | IGNORE_STATUSES


def _status_payload(line):
    parts = line.strip().split(None, 1)
    if not parts or parts[0] not in ALL_STATUSES:
        return None, None
    return parts[0], parts[1].strip() if len(parts) > 1 else ""


def _clean_nodeid(status, payload):
    if not payload:
        return ""
    if status == "SKIPPED":
        # SKIPPED lines are often: "[1] path/test.py:12: reason". They are
        # ignored by parse_results(), but keep this robust if callers inspect it.
        return payload
    if status in {"XFAIL", "XPASS", "FAILED", "ERROR"}:
        # pytest may append " - reason" in the short summary. The claim identity
        # is the nodeid, not the diagnostic suffix.
        payload = payload.split(" - ", 1)[0]
    return payload.strip()


def parse_results(stdout: str) -> list[tuple[str, bool]]:
    """Return ``[(nodeid, passed)]`` from pytest ``-rA`` output.

    Only the short-test-summary section is parsed. PASSED and XPASS count as
    pass; FAILED and ERROR count as fail; SKIPPED and XFAIL are omitted. If the
    same nodeid appears more than once, the last summary line wins while the
    nodeid keeps the order of its first appearance.
    """
    in_summary = False
    order = []
    results = {}
    for raw in (stdout or "").splitlines():
        line = raw.strip()
        if SUMMARY_HEADER in line:
            in_summary = True
            continue
        if not in_summary:
            continue
        status, payload = _status_payload(line)
        if status is None:
            continue
        if status in IGNORE_STATUSES:
            continue
        nodeid = _clean_nodeid(status, payload)
        if not nodeid:
            continue
        if nodeid not in results:
            order.append(nodeid)
        results[nodeid] = status in PASS_STATUSES
    return [(nodeid, results[nodeid]) for nodeid in order]
