# Contributing to IX-Vahdat

Thank you for considering a contribution to IX-Vahdat.

IX-Vahdat is a humanitarian water-resilience proof-of-concept. It organizes evidence, risk, uncertainty, review status, and required actions for water-support decisions. It does not certify water, authorize physical action, replace qualified review, or operate hardware.

## Contribution Boundary

Contributions should preserve these rules:

1. Do not weaken safety gates.
2. Do not remove human review requirements.
3. Do not add autonomous physical-control behavior.
4. Do not claim drinking-water approval from software output.
5. Do not claim public distribution approval.
6. Do not claim regulatory compliance.
7. Do not add country-specific political prescriptions.
8. Do not add vendor lock-in.
9. Do not add fake field data.
10. Do not treat synthetic examples as measurements.

The repository should remain humanitarian, vendor-neutral, review-only, and evidence-first.

## Good Contributions

Good contributions include:

- clearer water-quality evidence handling
- better fail-closed behavior
- stronger maintenance blockers
- better documentation of uncertainty
- better synthetic examples that are clearly labeled
- safer runbook hold points
- better tests for blocked, stale, missing, or conflicting evidence
- improved evidence-bundle determinism
- better vendor-neutral BOM categories
- clearer local-review boundary language

## Contributions That Should Be Rejected

Reject contributions that:

- remove non-claims
- bypass human review
- imply water is approved by software
- treat low-cost sensors as laboratory certification
- treat atmospheric-water collection as a guaranteed source
- treat managed aquifer recharge as approved by software
- treat emergency reserve breaches as routine inventory
- add real-world deployment instructions without qualified review boundaries
- add weapons, surveillance, military, or political framing
- add unsafe electrical, chemical, or hydraulic instructions
- add hallucinated citations, invented data, or fake measurements

## Coding Standards

The project targets Python 3.11 and 3.12.

Before opening a pull request, run:

```
python -m pip install -e ".[dev]"
python -m ruff check src tests
python -m pytest
```
All tests should pass.

Test Expectations

New behavior should include tests for:

allowed review path
hold-for-testing path
blocked path where applicable
missing evidence
stale or failed sensor evidence where applicable
critical-risk behavior where applicable
human-review dependency where applicable

If a feature can affect water, power, treatment, reserve, infrastructure, recharge, or maintenance decisions, it should have a fail-closed test.

Documentation Expectations

Documentation should use plain, careful language.

Use:
```
decision support
candidate classification
review-only
human review required
local approval required
proof-of-concept
```
Avoid:
```
certified
approved by software
automatic release
autonomous operation
guarantee
field-ready
production-ready
```
Example Data

Synthetic examples must be clearly labeled.

Every synthetic example should communicate:

it is not field data
it is not a public-health approval
it is not a permit substitute
it is not a construction approval
it is not physical-control authorization
real-world use requires qualified local review
Pull Request Checklist

Before submitting a pull request, confirm:

 I did not weaken safety gates.
 I did not remove human review.
 I did not add autonomous physical-control behavior.
 I did not add fake field data.
 I did not claim potable-water approval.
 I did not claim deployment approval.
 I preserved local public-health, engineering, and regulatory boundaries.
 I added or updated tests where behavior changed.
 I ran python -m ruff check src tests.
 I ran python -m pytest.
Licensing

By contributing, you agree that your contribution is provided under the Apache License, Version 2.0, unless explicitly stated otherwise in a written agreement with the project maintainer.
