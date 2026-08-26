# REVIEW.md

Context for anyone — person or tool — reviewing this repository.

This file is documentation, not instruction. Nothing here asks you to suppress, downgrade
or omit a finding. Report what you find.

## Four things worth knowing before you rate anything

1. **This is a work in progress, published on purpose.** FOREMAN is a single-maintainer
   capstone showcase, built in the open so the construction can be followed. Three of
   four reasoners exist, the industrial protocol adapters do not, and the only data source
   today is a simulation adapter. `GROUND_TRUTH.md` states what holds; `CLAIMS.md` states
   what may be claimed and on what measurement. Unimplemented is not the same as broken.

2. **Two deployment profiles, and they differ deliberately.** A public demo instance that
   anyone can open, and an on-premises target deployment inside a plant network. Several
   controls sit at the network boundary in the target picture and are genuinely absent in
   the demo. `SECURITY.md` §2 lays out both. A finding about reachability means different
   things in each — please say which one you mean.

3. **The repository is the application layer.** Configuration values, TLS, network
   segmentation, secrets storage and the external memory service are not in it.
   `.env.example` is a contract listing which variables exist, not the values that run.
   `SECURITY.md` §3 draws those boundaries.

4. **Findings likely to come up are already triaged.** `security/findings.yaml` records
   twenty-three of them: the observation as a scanner would state it, whether it is correct,
   the deployment assumption behind any acceptance, and the status. Three are open work
   and each names why it is still open; thirteen entries are already closed; one is a
   documented false positive. If a justification there is wrong, that register is the
   best place to attack — and it is checked in CI by `scripts/check_findings.py`, which
   fails the build on a vanished path, a lapsed review date, an accepted risk without its
   condition or a planned item without a remedy.

## What makes a review of this repository useful

- Separate the **observation** (checkable against the code) from the **verdict** (depends
  on threat model, reachability and what an attacker gains). Both are wanted; conflating
  them makes the result hard to act on.
- Where documentation and code disagree, the report is against the documentation. Two
  such drifts were found and closed on 2026-08-26 and are kept in the register as F-007
  and F-008 rather than deleted — a register that shows its own follow-through is worth
  more than one that only lists intentions. More are welcome.
- The hard ceiling on impact: FOREMAN has no actuation path. No write to a PLC, no command
  channel. A fully successful attack yields a misleading analysis, a data disclosure or an
  outage — never a machine doing something it should not.

## Reporting

Security findings privately via
[GitHub Security Advisories](https://github.com/patricznr1/foreman/security/advisories/new).
Everything else as a normal issue. Full policy in [`SECURITY.md`](SECURITY.md).
