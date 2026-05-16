# Regulatory and Safety Boundaries

IX-Vahdat is a software proof-of-concept for humanitarian water-resilience decision support. It is not a regulatory compliance product.

This document defines the boundaries that every implementation, fork, field adaptation, demo, and report should preserve.

## No Approval by Software Alone

No IX-Vahdat output should be treated as:

- drinking-water approval
- public distribution approval
- treatment-system approval
- water discharge approval
- construction approval
- managed aquifer recharge approval
- atmospheric-water harvesting approval
- electrical-system approval
- emergency response approval
- procurement approval
- field deployment approval

All physical action requires qualified local review and applicable legal approval.

## Required Authorities May Include

Depending on location and use case, real projects may need review from:

- public-health authorities
- water-quality laboratories
- civil engineers
- electrical engineers
- environmental engineers
- hydrogeologists
- geotechnical engineers
- local permitting authorities
- emergency managers
- community representatives
- site owners or operators
- legal counsel

This repository does not identify every authority required in every jurisdiction.

## Water Quality

Water quality decisions require qualified testing and interpretation.

Software readings, low-cost sensors, portable meters, or synthetic examples cannot certify water as safe for drinking.

At minimum, real projects must consider local requirements for:

- microbiological indicators
- turbidity
- salinity and conductivity
- pH
- chemical contaminants
- heavy metals where relevant
- treatment validation
- disinfection residuals where applicable
- storage hygiene
- sample handling and chain of custody
- repeated testing over time

## Treatment and Reuse

Treatment routing in IX-Vahdat is review-only.

A route such as `pass_to_review`, `recirculate`, `hold_for_testing`, or `reject_to_waste_review` does not operate a treatment system or approve water use.

Treatment and reuse require local public-health and environmental review.

## Discharge and Disposal

Water that fails quality gates, chemical screens, pathogen screens, or contamination checks may require disposal review.

IX-Vahdat does not approve discharge to soil, drains, rivers, groundwater, sewer systems, wetlands, canals, roads, or public spaces.

## Managed Aquifer Recharge

Managed aquifer recharge is high-consequence.

Improper recharge can spread contamination, mobilize salts, damage aquifers, worsen subsidence, or create legal and environmental harm.

IX-Vahdat’s recharge screen must remain conservative. It should hold or block unless all required source-water, site, hydrogeology, monitoring, environmental, local authority, and community review conditions are satisfied.

## Atmospheric Water Harvesting

Atmospheric-water harvesting outputs are climate and site triage only.

They do not guarantee yield, certify water quality, select vendors, or authorize deployment.

Collected atmospheric water can still become contaminated by air pollution, dust, surfaces, filters, tanks, biofilm, sorbents, condensers, or handling.

## Energy and Power

Energy accounting and power-priority logic do not certify electrical safety.

Real electrical systems require qualified design, protection, wiring, grounding, fusing, batteries, enclosures, weatherproofing, and local code compliance.

IX-Vahdat’s power model should protect critical evidence logging and sensing before optional loads, but it must not be used as a relay controller without independent engineering design and safety validation.

## Infrastructure

Infrastructure-health modules do not certify structural safety.

Physical assets such as tanks, pipes, pumps, mounts, panels, drains, channels, frames, and skids require inspection, design, maintenance, and local engineering review.

A software `normal` or `reviewable` state is not a structural certificate.

## Emergency Use

Emergency review outputs do not authorize public distribution.

Emergency use can change risk tolerance, but it does not remove the need for human authority, documentation, water-quality caution, and local emergency procedures.

## Humanitarian Neutrality

IX-Vahdat should be framed as drought-stressed community water-resilience support.

It should not be framed as:

- a geopolitical prescription
- a national policy directive
- a sanction bypass tool
- a military tool
- an intelligence tool
- a tool for political leverage
- a tool that instructs a government or population what to do

The repository should stand on its own as humanitarian, review-only, vendor-neutral software.

## Required Language in Reports

Reports, demos, and evidence bundles should include language equivalent to:

```
This output is decision support only. It does not certify water as potable,
approve public distribution, replace licensed engineering or public-health
review, issue permits, authorize construction, authorize discharge, authorize
managed aquifer recharge, or control physical systems autonomously.
```

Final Boundary

IX-Vahdat may help people ask better questions and preserve better evidence.

It must not be used to pretend that software can replace measurement, maintenance, engineering, public-health review, community review, or lawful local approval.
