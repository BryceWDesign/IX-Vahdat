# Safety Policy

IX-Vahdat is designed around conservative safety gates, evidence discipline, human review, and blocked action when evidence is missing or unsafe.

The project should fail closed.

## Core safety principles

1. No potable-water claim without evidence.
2. No public-use claim without human review.
3. No autonomous physical action.
4. No discharge, recharge, or distribution approval from software alone.
5. No use of stale, failed, unverified, missing, or conflicting sensor data as proof.
6. No hidden uncertainty.
7. No field deployment without maintenance planning.
8. No high-risk intervention without local authority and qualified review.
9. No country-specific policy prescription.
10. No miracle-water framing.

## Required human review

IX-Vahdat outputs are decision-support records only.

Human review is required before:

- drinking-water use
- hygiene use
- irrigation use
- utility use
- public distribution
- emergency allocation
- treatment bypass
- treatment-route change
- storage-tank release
- wastewater reuse
- managed aquifer recharge
- environmental discharge
- field construction
- infrastructure repair
- excavation or thermal-assisted excavation research

## Required blocking behavior

The system must block or hold for testing when any of the following conditions are present:

- missing pH evidence
- missing turbidity evidence
- missing conductivity evidence
- stale sensor data
- failed sensor data
- unverified sensor data
- conflicting evidence
- pathogen indicator present
- failed chemical screen
- suspicious water-quality reading
- tank contamination risk
- treatment-chain uncertainty
- filter clog warning
- pump fault
- unsafe pressure state
- low battery affecting safety-critical functions
- insufficient energy accounting
- maintenance overdue
- missing reviewer identity for high-impact action
- unclear destination for treated or rejected water
- unsupported claim of potable water

## Water-use classification posture

IX-Vahdat may classify water only into conservative candidate classes:

- `drinking_candidate`
- `hygiene_candidate`
- `irrigation_candidate`
- `utility_water`
- `unsafe_hold`

These are triage classes, not certifications.

A `drinking_candidate` result means:

- evidence passed configured proof-of-concept triage thresholds
- disinfection evidence was present
- pathogen evidence did not indicate contamination
- chemical screen evidence did not indicate failure
- human review is still required
- local public-health requirements still control

An `unsafe_hold` result means:

- use is blocked or held
- treatment, disposal review, or further testing is required
- no public-use claim should be made

## Evidence requirements

Every reviewable decision should preserve:

- site identifier
- timestamp
- measured inputs
- measurement units
- source sensor or observer identity
- evidence quality
- sensor status
- configured thresholds
- decision status
- reasons
- required actions
- uncertainty notes
- reviewer status
- final human decision when available

## Maintenance as safety

Maintenance is not optional.

The following conditions must be treated as safety blockers when relevant:

- expired filters
- clogged filters
- UV lamp overdue or failed
- unclean storage tank
- failed tank inspection
- pump fault
- leaking tank or line
- degraded battery
- solar input failure affecting critical loads
- uncalibrated pH sensor
- uncalibrated conductivity sensor
- uncalibrated turbidity sensor
- damaged fog mesh
- contaminated collection surface
- sorbent cartridge overdue
- missing spare parts for critical treatment steps

## Energy safety

Water decisions must not ignore energy.

The system should account for:

- available power
- battery reserve
- critical load priority
- energy per liter
- treatment energy
- pumping energy
- sensor and telemetry energy
- emergency reserve protection
- degraded-mode operation

If energy evidence is missing or insufficient for safety-critical functions, the system should block or hold high-impact decisions.

## Atmospheric water harvesting safety

Atmospheric water harvesting outputs must not be treated as automatically potable.

Collected water may require:

- particulate filtration
- disinfection
- remineralization
- storage hygiene controls
- microbial testing
- chemical screening
- air-quality review
- human approval

Low yield, poor climate fit, dust, smoke, industrial pollutants, contaminated collection surfaces, or insufficient energy may make atmospheric harvesting unsuitable for a site.

## Field-treatment safety

Field treatment must not be treated as universal contaminant destruction.

The system must not claim to remove all contaminants.

Treatment-route logic should preserve conservative outcomes:

- pass to human review only when evidence supports it
- recirculate when treatment is incomplete but potentially recoverable
- hold when evidence is missing or uncertain
- reject when indicators exceed safety limits or failure conditions exist

## Thermal-assisted excavation research boundary

IX-Vahdat may include a feasibility gate for thermal-assisted mechanical excavation research.

That gate is not an excavation controller.

It must evaluate only whether a proposed rock-removal method is physically plausible, energy-accounted, geotechnically monitored, environmentally bounded, and human-reviewable before any field action is considered.

It must not provide autonomous actuation, field-control sequencing, or instructions for unsafe excavation.

## Safe failure posture

When the system is unsure, it should choose one of the following:

- `hold_for_testing`
- `block`
- `unsafe_hold`
- `human review required`
- `qualified inspection required`
- `local authority required`

The system should not convert uncertainty into permission.
