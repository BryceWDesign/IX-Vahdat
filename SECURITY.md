# Security and Safety Policy

IX-Vahdat is a humanitarian water-resilience proof-of-concept. Security for this project includes software security, evidence integrity, and safety-boundary preservation.

## Supported Status

IX-Vahdat is pre-alpha proof-of-concept software.

It is not a certified water system, not a public-health approval, not a permit substitute, not a construction approval, not a field-use approval, and not an autonomous controller.

Use it for review-only software evaluation unless qualified local reviewers approve a separate real-world process.

## Report Security Issues

Please report issues involving:

- unsafe water-use claims
- missing human-review gates
- evidence-bundle tampering risks
- receipt hash or determinism problems
- stale or missing sensor evidence being accepted incorrectly
- unsafe emergency reserve behavior
- unsafe managed-aquifer-recharge behavior
- unsafe atmospheric-water claims
- command-line output that implies physical approval
- documentation that overstates what the project can do

Do not publish exploit details for an active safety issue until maintainers have had time to evaluate and respond.

## Safety-Critical Issue Examples

Treat these as high priority:

- software says water is approved without human review
- unsafe-hold water can pass as a candidate use
- critical maintenance failures do not block
- active critical failure modes do not fail closed
- safety-critical infrastructure leaks do not block
- protected emergency reserve can be routinely breached
- managed aquifer recharge can proceed without required review
- synthetic examples can be mistaken for field data
- evidence receipts can be changed without hash drift
- CLI output implies certification, public use, or hardware authority

## Out of Scope

This repository does not provide:

- hardware relay control
- pump automation
- valve automation
- chemical dosing automation
- UV control automation
- recharge operation automation
- public water distribution automation
- emergency response automation

Requests to add those features should be rejected unless the project scope is formally changed and reviewed by qualified domain experts.

## Responsible Use

Do not use IX-Vahdat to bypass:

- water-quality testing
- public-health review
- civil engineering review
- electrical engineering review
- environmental review
- hydrogeology review
- local permits
- community consent
- emergency authority

IX-Vahdat can organize evidence. It cannot replace accountability.

## Evidence Integrity

When exporting receipts or bundles:

- preserve timestamps
- preserve source IDs
- preserve evidence quality
- preserve sensor status
- preserve uncertainty notes
- preserve reviewer status
- preserve content hashes
- archive exported bundles when used in review

If evidence changes, generate a new receipt or bundle rather than editing an old one silently.

## Disclosure Preference

When reporting a safety or security issue, include:

- affected module or document
- expected safe behavior
- observed unsafe behavior
- minimal reproduction steps
- proposed fix if known
- whether the issue affects synthetic examples, tests, docs, or runtime code

Avoid including real personal, medical, facility, or sensitive infrastructure data in reports.
