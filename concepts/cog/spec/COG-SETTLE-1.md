# COG-SETTLE-1 Settlement Specification

Status: Draft 1

## 1. Arithmetic

All prices and money MUST be calculated with decimal arithmetic. Fixes are
rounded to six decimal places and payable amounts to two decimal places with
`ROUND_HALF_UP`. Binary floating-point MUST NOT be used for settlement.

## 2. Normal rule

The Settlement Fix is the median of eligible daily COG-1 fixes in the seven
calendar days ending on the invoice date. Four or more observations produce
status `normal`.

## 3. Unavailability ladder

Each invoice MUST label the rung used:

1. One to three observations in seven days extend the window to fourteen days
   and use status `degraded-window`; counterparty acknowledgement is required.
2. No observation in fourteen days carries the latest eligible local fix
   forward through day 44 with status `carry-forward`.
3. From day 45 through day 89, another named publisher is tried first. If none
   is available, a blend-normalized external anchor MAY produce status
   `anchor-fallback`. It is provisional, requires acknowledgement, is not
   payable before acknowledgement, and MUST be trued up on the first invoice
   after eligible local publication resumes.
4. At day 90, remaining cogs convert to USD at the last eligible local fix.
   Status `converted` is payable and terminal after acknowledgement; it is not
   later trued up.

External anchors and bundled snapshots MUST NOT silently satisfy `min_tier`.

## 4. Evidence

Every used archive MUST carry its SHA-256 digest and signature-verification
result. The invoice MUST identify its obligation, period, fix observations,
publisher, tier, window, rounding rule, and unavailability status. It MUST
include a repository-root command that independently recomputes and verifies
the invoice from local archives.

## 5. Signatures

An invoice's identifier is the canonical SHA-256 of the document excluding
`invoice_id` and `signatures`. Detached SSH signatures use namespace
`cog-invoice`. A CDO detached signature uses namespace `cog-cdo`.
