# IX-Vahdat Assembly and Commissioning Guidance

This document provides a review-only assembly and commissioning structure for IX-Vahdat water-resilience nodes.

It is not a construction manual, electrical approval, public-health approval, potable-water certification, discharge authorization, recharge authorization, or field-deployment authorization.

## Operating Principle

IX-Vahdat should be assembled and tested in this order:

1. non-claims acknowledgment
2. dry assembly
3. sensor calibration
4. power and safe-hold test
5. maintenance-readiness check
6. infrastructure-health check
7. water-quality evidence check
8. treatment-routing review
9. reserve-protection review
10. optional atmospheric-water triage
11. optional managed-aquifer-recharge readiness screen
12. evidence bundle export
13. human review

No water should be released, distributed, discharged, injected, or called potable from software output alone.

## Phase 0: Boundary Review

Before assembly, the team should confirm:

- this is a proof-of-concept
- water is not certified as potable
- public-health review is required for drinking-water decisions
- local engineering review is required for physical systems
- electrical safety review is required for energized systems
- environmental review is required for discharge or recharge concepts
- community and local authority review may be required
- no autonomous control is enabled
- emergency reserve logic is protected

Required evidence:

- signed non-claims checklist
- reviewer name or role
- date and scope of review
- list of physical actions explicitly not authorized

Hold point:

- do not continue to wet testing until non-claims are understood

## Phase 1: Dry Assembly

Dry assembly means no public-use water and no public distribution.

Tasks:

- inventory components
- label tanks and lines
- label unsafe/hold/review-only containers
- mount sensors without relying on their readings yet
- mount power components without energizing optional loads
- route tubes and valves visibly
- identify sample ports
- identify reject/hold routing
- identify cleaning access
- prepare spill control

Required evidence:

- component inventory
- photographs or inspection notes
- tank labels
- line labels
- power-load list
- maintenance items list

Hold point:

- do not energize pumps, UV, active condensation, or other optional loads until power review passes

## Phase 2: Sensor Calibration and Evidence Setup

Tasks:

- calibrate pH meter
- verify conductivity meter
- verify turbidity meter
- verify temperature measurement
- identify pathogen testing method
- identify chemical screening method
- verify timestamps are timezone-aware
- verify sensor IDs and source IDs are recorded
- verify stale, failed, unverified, missing, or conflicting evidence holds the system

Required evidence:

- calibration records
- sensor IDs
- measurement timestamps
- evidence-quality labels
- sensor-status labels
- sample handling process

Hold point:

- do not classify water-use candidates until required measurements are present

## Phase 3: Power and Safe-Hold Review

Tasks:

- list all electrical loads
- classify loads as critical, important, deferrable, or nonessential
- identify safe-hold loads
- verify evidence logger can remain powered
- verify water-quality sensors can remain powered
- verify protected battery reserve
- verify optional loads can be shed
- verify fusing, disconnects, and enclosure plan under qualified review

Required evidence:

- load list
- power budget
- battery reserve setting
- safe-hold load list
- energy boundary description
- qualified electrical review note where applicable

Hold point:

- do not run optional loads when critical load margin or reserve is not protected

## Phase 4: Maintenance Readiness

Tasks:

- list all filters
- list UV components if used
- list tanks
- list pumps
- list sensors
- list batteries
- list solar inputs
- list fog mesh, AWH panel, or sorbent components if used
- record service intervals
- record hours since service
- identify spares and consumables
- mark overdue, failed, stale, unverified, or missing evidence as blockers

Required evidence:

- maintenance item registry
- service intervals
- inspection records
- spare-parts list
- cleaning plan

Hold point:

- failed critical maintenance blocks dependent water-support decisions

## Phase 5: Infrastructure-Health Review

Tasks:

- inspect tanks
- inspect pipes
- inspect pumps
- inspect valves
- inspect panel mounts
- inspect fog mesh frames if used
- inspect drains or channels if used
- check leaks
- check corrosion
- check deformation
- check pressure anomalies
- check vibration
- check contamination pathways

Required evidence:

- asset observations
- observation timestamps
- asset IDs
- health state
- evidence quality
- sensor status
- leak status
- critical-to-water-safety flag

Hold point:

- safety-critical leaks block dependent water-support decisions

## Phase 6: Water-Quality Gate

Tasks:

- measure pH
- measure turbidity
- measure conductivity or salinity
- measure temperature
- verify pathogen indicator path
- verify chemical screen path
- verify disinfection status if relevant
- classify evidence quality
- classify sensor status
- record reasons and required actions

Required evidence:

- water-quality measurements
- sample source
- timestamp
- calibration state
- pathogen indicator result or hold reason
- chemical screen result or hold reason
- disinfection verification or hold reason

Hold point:

- missing, stale, conflicting, pathogen-positive, chemically failed, or unverified data should hold or block

## Phase 7: Treatment-Routing Review

Tasks:

- check pretreatment availability
- check filtration availability
- check disinfection availability
- check storage cleanliness
- check recirculation availability
- check waste-hold availability
- check filter pressure differential
- check flow rate
- check tank capacity remaining

Possible software outputs:

- `pass_to_review`
- `recirculate`
- `hold_for_testing`
- `reject_to_waste_review`

Hold point:

- none of these outputs is release authorization

## Phase 8: Emergency Reserve Review

Tasks:

- measure stored volume
- define protected reserve volume
- define daily priority demand
- evaluate requested release volume
- verify water-use class
- verify quality gate passed
- verify treatment route reviewed
- verify tank integrity
- verify storage age
- identify whether request is routine or emergency

Hold point:

- routine release should not breach protected reserve
- emergency breach requires explicit emergency human authorization

## Phase 9: Atmospheric-Water Review

Atmospheric-water modules are optional.

Tasks:

- measure relative humidity
- measure temperature
- measure dew point
- measure wind speed
- measure solar irradiance
- assess fog signal
- assess air quality
- assess dust risk
- assess collection area
- assess maintenance capacity
- assess storage capacity
- assess power availability for active condensation

Possible review modes:

- fog capture
- radiative dew
- MOF or sorbent adsorption
- hydrogel/salt adsorption
- solar desorption
- active condensation
- hold for testing
- do not deploy AWH

Hold point:

- climate fit is not a water-yield guarantee
- collected water still requires treatment and testing

## Phase 10: Managed Aquifer Recharge Screen

Managed aquifer recharge is optional and high-consequence.

Tasks:

- verify source-water quality
- verify treatment route
- verify salinity risk
- verify contamination risk
- verify method
- verify infiltration capacity
- verify groundwater vulnerability
- verify geotechnical stability
- verify subsidence risk
- verify monitoring well or equivalent observation
- verify environmental review
- verify local authority review
- verify community review

Hold point:

- software must not authorize recharge
- injection wells require specialist design and approval
- missing review blocks

## Phase 11: Evidence Bundle Export

Tasks:

- generate receipts for major gates
- export deterministic evidence bundle
- preserve content hash
- record reviewer status
- record uncertainty
- include non-claims

Required evidence:

- JSON receipts
- JSON bundle
- bundle hash
- reviewer status
- required actions

Hold point:

- an evidence bundle is not certification or deployment approval

## Phase 12: Human Review

Tasks:

- assign qualified reviewer
- record reviewer identity
- record reviewer role
- record authority basis
- record decision
- record limits
- record open blockers
- record next review date if applicable

Possible review outcomes:

- not reviewed
- rejected
- changes requested
- approved for limited use

Hold point:

- no field action should proceed without proper human authority

## Commissioning Exit Criteria

A node may continue only to limited human review when:

- all critical maintenance is reviewable
- no active critical failure mode is present
- no safety-critical infrastructure leak is present
- safe-hold power loads are protected
- water-quality evidence is complete enough for the claimed candidate use
- treatment route is reviewable
- reserve logic is protected
- evidence bundle is exported
- human review is recorded
- local requirements are understood

Even then, the result is limited review, not certification.

## Required Final Statement

Every commissioning report should include:

```
This commissioning record is decision support only. It does not certify water
as potable, approve public distribution, replace licensed engineering or
public-health review, issue permits, authorize construction, authorize
discharge, authorize managed aquifer recharge, or control physical systems
autonomously.
```

`tests/test_docs_content.py`

```
from pathlib import Path


DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"


def _read_doc(name: str) -> str:
    return (DOCS_DIR / name).read_text(encoding="utf-8")


def test_build_tiers_doc_preserves_non_authorizing_boundary() -> None:
    text = _read_doc("BUILD_TIERS_AND_BOM.md").lower()

    assert "not a procurement quote" in text
    assert "not a vendor recommendation" in text
    assert "not a certified drinking-water plant" in text
    assert "do not publish a false universal cost" in text
    assert "a bom is not a system" in text


def test_build_tiers_doc_covers_all_required_deployment_tiers() -> None:
    text = _read_doc("BUILD_TIERS_AND_BOM.md")

    assert "Tier 1: Demo Node" in text
    assert "Tier 2: School or Clinic Node" in text
    assert "Tier 3: Community Node" in text
    assert "Tier 4: Advanced Hub" in text


def test_assembly_doc_preserves_hold_points_and_human_review() -> None:
    text = _read_doc("ASSEMBLY_AND_COMMISSIONING.md").lower()

    assert "hold point" in text
    assert "human review" in text
    assert "no water should be released" in text
    assert "software must not authorize recharge" in text
    assert "none of these outputs is release authorization" in text


def test_assembly_doc_contains_final_required_statement() -> None:
    text = _read_doc("ASSEMBLY_AND_COMMISSIONING.md")

    assert "This commissioning record is decision support only." in text
    assert "does not certify water" in text
    assert "does not certify water\nas potable" in text
    assert "control physical systems\nautonomously" in text


def test_docs_do_not_claim_certification_or_field_authorization() -> None:
    forbidden_phrases = (
        "certified potable",
        "approved for public distribution",
        "field deployment authorized",
        "safe to drink",
        "guaranteed yield",
    )

    for path in sorted(DOCS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden_phrases:
            assert phrase not in text
```

