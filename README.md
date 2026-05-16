# IX-Vahdat

Humanitarian water-resilience proof-of-concept for drought-stressed and infrastructure-stressed communities.

IX-Vahdat organizes water-support evidence into conservative review gates: water-quality screening, water-use candidate classification, treatment routing, atmospheric-water triage, energy accounting, power priority, emergency reserve protection, maintenance readiness, infrastructure-health screening, managed aquifer recharge screening, runbook hold points, human review, receipts, evidence bundles, and vendor-neutral BOM planning.

It is designed to make uncertainty visible.

It does **not** certify water, approve public use, replace licensed review, issue permits, authorize construction, authorize discharge, authorize managed aquifer recharge, or operate physical systems autonomously.

## Status

Pre-alpha software proof-of-concept.

This repository is suitable for:

- software review
- safety-gate review
- synthetic demo runs
- evidence-flow design
- humanitarian water-resilience planning
- conservative decision-support prototyping

It is not suitable for direct field use without qualified local review, real measurements, site-specific engineering, public-health review, environmental review where applicable, and lawful local approval.

## Core Rule

```
Software may organize evidence. Qualified humans must decide.
```
IX-Vahdat can say that evidence may continue to review.

It must not pretend that software alone can make final water-safety, distribution, discharge, recharge, construction, or emergency-response decisions.

What IX-Vahdat Does

IX-Vahdat provides Python modules for:

Area	Purpose
Water quality	Evaluate measured pH, turbidity, conductivity, temperature, pathogen indicator, chemical screen, and disinfection evidence
Water-use classes	Classify water as a candidate only: drinking candidate, hygiene candidate, irrigation candidate, utility water, or unsafe hold
Treatment routing	Route batches to review, recirculation, testing hold, or waste/disposal review
Atmospheric water	Triage fog, dew, sorbent, hydrogel, solar-desorption, and active-condensation concepts
Energy accounting	Calculate energy input and energy per liter from measured or estimated evidence
Energy portfolio	Compare water-support paths by energy per liter without treating efficiency as safety
Power priority	Protect evidence logging, water-quality sensing, safe-hold loads, and emergency battery reserve
Emergency reserve	Prevent protected reserve water from being treated as routine inventory
Maintenance	Block or hold on failed filters, UV, tanks, sensors, pumps, batteries, panels, sorbents, and mounts
Failure modes	Evaluate stale sensors, contamination risks, filter clogging, storage faults, pump faults, low power, and governance failures
Infrastructure health	Screen tanks, pipes, pumps, panels, mounts, drains, valves, and other physical assets
Managed aquifer recharge	Screen source water, site evidence, monitoring, hydrogeology risk, and required reviews
Site readiness	Combine upstream gates into a conservative site-readiness class
Human review	Require named human review before limited-use review can proceed
Receipts	Create deterministic JSON evidence receipts
Bundles	Package receipts into deterministic review bundles with content hashes
BOM planning	Estimate vendor-neutral cost ranges from caller-supplied local cost inputs
Runbooks	Evaluate assembly and commissioning steps with evidence and hold points
CLI demo	Print a deterministic synthetic JSON demo payload

What IX-Vahdat Does Not Do

IX-Vahdat does not:

certify water as potable
approve drinking use
approve public distribution
approve emergency release
approve discharge
approve managed aquifer recharge
approve construction
approve procurement
approve electrical systems
approve treatment systems
approve atmospheric-water harvesting systems
guarantee water yield
guarantee cost
guarantee local availability of parts
replace laboratory testing
replace public-health review
replace civil, electrical, geotechnical, environmental, or hydrogeology review
operate pumps
operate valves
operate UV systems
operate chemical dosing
operate recharge hardware
operate atmospheric-water hardware
control physical systems autonomously

Repository Layout
```
.
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── ASSEMBLY_AND_COMMISSIONING.md
│   ├── BUILD_TIERS_AND_BOM.md
│   ├── HUMANITARIAN_SCOPE.md
│   ├── NON_CLAIMS.md
│   ├── REGULATORY_BOUNDARIES.md
│   └── SAFETY_MODEL.md
├── examples/
│   └── site_configs/
│       ├── synthetic_hold_for_testing_node.json
│       └── synthetic_reviewable_node.json
├── src/
│   └── ix_vahdat/
│       ├── __init__.py
│       ├── asset_checks.py
│       ├── atmospheric.py
│       ├── awh.py
│       ├── awh_scoring.py
│       ├── bom.py
│       ├── bundles.py
│       ├── cli.py
│       ├── domain.py
│       ├── energy.py
│       ├── energy_profile.py
│       ├── failures.py
│       ├── infrastructure.py
│       ├── maintenance.py
│       ├── power.py
│       ├── quality.py
│       ├── receipts.py
│       ├── recharge.py
│       ├── reserve.py
│       ├── review.py
│       ├── runbooks.py
│       ├── site_readiness.py
│       ├── treatment.py
│       ├── version.py
│       └── water_use.py
├── tests/
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE
├── NOTICE
├── pyproject.toml
├── README.md
└── SECURITY.md
```

Install
```
python -m pip install -e ".[dev]"
```
Requires Python 3.11 or newer.

Run Tests
```
python -m ruff check src tests
python -m pytest
```
The GitHub Actions workflow runs:

Ruff linting
tests on Python 3.11
tests on Python 3.12
CLI smoke test
Run the Synthetic Demo

```
ix-vahdat demo --pretty
```
The demo prints deterministic JSON.

Important: the demo is synthetic. It is not field data, not a public-health record, not a site approval, and not a physical-operation instruction.

Minimal Python Example
```
from datetime import UTC, datetime

from ix_vahdat import (
    DecisionStatus,
    EvidenceQuality,
    Measurement,
    SensorStatus,
    WaterQualitySnapshot,
    classify_water_use,
    evaluate_water_quality_gate,
)

observed_at = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)

snapshot = WaterQualitySnapshot(
    ph=Measurement(
        name="ph",
        value=7.2,
        unit="pH",
        source_id="meter-1",
        timestamp=observed_at,
        quality=EvidenceQuality.MEASURED,
        sensor_status=SensorStatus.OK,
    ),
    turbidity_ntu=Measurement(
        name="turbidity",
        value=0.6,
        unit="NTU",
        source_id="meter-2",
        timestamp=observed_at,
        quality=EvidenceQuality.MEASURED,
        sensor_status=SensorStatus.OK,
    ),
    conductivity_us_cm=Measurement(
        name="conductivity",
        value=650.0,
        unit="uS/cm",
        source_id="meter-3",
        timestamp=observed_at,
        quality=EvidenceQuality.MEASURED,
        sensor_status=SensorStatus.OK,
    ),
    temperature_c=Measurement(
        name="temperature",
        value=20.0,
        unit="C",
        source_id="meter-4",
        timestamp=observed_at,
        quality=EvidenceQuality.MEASURED,
        sensor_status=SensorStatus.OK,
    ),
    e_coli_present=False,
    chemical_screen_passed=True,
    disinfection_verified=True,
)

quality_result = evaluate_water_quality_gate(snapshot, evaluated_at=observed_at)
use_result = classify_water_use(snapshot)

assert quality_result.decision_status is DecisionStatus.ALLOW_REVIEW

print(use_result.use_class.value)
print(use_result.required_actions)
```

This example does not approve water for drinking. It only shows how evidence can continue to review.

Decision Statuses

IX-Vahdat uses three conservative decision statuses:

Status	Meaning
allow_review	Evidence may continue to qualified human review
hold_for_testing	More evidence, service, inspection, or review is required
block	The dependent decision should stop under current evidence

allow_review is not final approval.

Risk Levels

IX-Vahdat uses four risk levels:

Risk	Meaning
low	No current gate blocker identified in the supplied evidence
moderate	Reviewable but caution, due-soon service, warning condition, or estimated evidence exists
high	Testing, service, investigation, or explicit human review is needed
critical	Current evidence should block the dependent decision
Water-Use Classes

IX-Vahdat may classify water as:

Class	Meaning
drinking_candidate	Candidate for qualified review only; not certified drinking water
hygiene_candidate	Candidate for hygiene review only
irrigation_candidate	Candidate for irrigation review only
utility_water	Candidate for non-contact utility use review only
unsafe_hold	Hold, treatment, disposal review, or additional testing required

A candidate class is not final use approval.

Atmospheric-Water Stack

IX-Vahdat can evaluate atmospheric-water collection concepts such as:

fog capture
radiative dew
MOF or sorbent adsorption
hydrogel or salt-composite adsorption
solar desorption
active condensation

The atmospheric-water logic considers:

relative humidity
dew point
fog signal
wind speed
solar irradiance
dust risk
air quality
collection area
storage capacity
maintenance capacity
power availability
battery state

The result is climate and site triage only. It does not guarantee yield or certify water quality.

Collected water still needs treatment, storage hygiene, maintenance, testing, and human review.

Managed Aquifer Recharge

IX-Vahdat includes a conservative managed aquifer recharge readiness screen.

It evaluates:

source-water class
quality-gate status
treatment-route review
salinity risk
contamination risk
recharge method
infiltration capacity
groundwater vulnerability
geotechnical stability
subsidence risk
monitoring availability
local authority review
environmental review
community review

The MAR screen must remain review-only.

It must not be used to authorize infiltration, injection, discharge, recharge, or construction.

Evidence Receipts

Receipts preserve:

receipt kind
timestamp
site metadata
decision status
risk level
evidence inputs
thresholds
reasons
required actions
uncertainty notes
reviewer status
metadata
deterministic content hash

Receipts are useful because they make a recommendation inspectable.

They are not legal approvals or certifications.

Evidence Bundles

Evidence bundles group receipts into deterministic JSON packages.

Bundles include:

bundle ID
site metadata
decision status
risk level
receipt snapshots
receipt hashes
non-claims
required actions
metadata
bundle content hash

If evidence changes, create a new receipt or bundle. Do not silently edit an old bundle.

BOM Planning

The BOM estimator totals caller-supplied cost ranges.

It supports planning tiers:

demo node
school or clinic node
community node
advanced hub

Cost outputs are planning estimates only.

They are not quotes, vendor recommendations, purchase orders, complete engineering BOMs, or local availability guarantees.

Assembly and Commissioning

The runbook model evaluates review-only steps such as:

safety brief
inventory check
assembly
sensor calibration
water-quality check
energy check
power check
maintenance check
infrastructure check
evidence export
human review
hold point

A completed runbook does not authorize physical operation. It means the runbook evidence may continue to qualified review.

Build Tiers

IX-Vahdat documentation describes four planning tiers.

Tier	Description
Demo node	Bench-scale proof-of-concept and training node
School or clinic node	Limited local review concept for small facilities
Community node	Larger local review concept with storage, treatment review, telemetry, and reserve logic
Advanced hub	Multi-path resilience site concept with stronger monitoring and evidence handling

These tiers are planning categories, not deployment approvals.

Example Configs

Example configs live under:
```
examples/site_configs/
```
They are synthetic and non-authorizing.

They exist to show expected data shape and review flow.

Do not present them as field data.

Safety Model

IX-Vahdat prefers false holds over false approvals.

The project should hold or block when evidence is:

missing
stale
failed
unverified
conflicting
outside configured thresholds
critical-risk
lacking human review
lacking local review where required

The safest default is:
```
hold for testing
block critical hazards
require human review
preserve evidence
do not overclaim
```
Humanitarian Scope

IX-Vahdat is country-neutral and community-centered.

Acceptable framing:
```
drought-stressed communities
infrastructure-stressed communities
humanitarian water resilience
review-only water evidence support
community-scale water decision support
```
Avoid framing that implies:

software solves a national water crisis
software replaces local institutions
software replaces public-health review
software authorizes physical systems
a repo is a substitute for governance, maintenance, measurement, or law
Development

Install development dependencies:
```
python -m pip install -e ".[dev]"
```
Run Checks:
```
python -m ruff check src tests
python -m pytest
```
Run CLI Demo:
```
ix-vahdat demo --pretty
```
Contribution Rules

Contributions should preserve:

fail-closed behavior
human review
non-claims
synthetic-data labeling
evidence quality
sensor status
deterministic receipts and bundles
local review boundaries
humanitarian neutrality
vendor neutrality

Contributions should not:

weaken safety gates
bypass human review
add autonomous physical-control behavior
add fake field data
imply water is approved by software
imply public distribution approval
imply regulatory compliance
imply guaranteed yield
add country-specific political prescriptions
add vendor lock-in
License

Apache License, Version 2.0.

See LICENSE and NOTICE.

Author

Bryce Lovell

Final Boundary

IX-Vahdat helps organize water-resilience evidence.

It does not replace measurement, maintenance, engineering, public-health review, environmental review, community review, local authority, or lawful approval.
