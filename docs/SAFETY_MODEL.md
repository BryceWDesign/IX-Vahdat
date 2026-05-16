# IX-Vahdat Safety Model

IX-Vahdat uses a conservative safety model:

```
Missing evidence should hold.
Conflicting evidence should hold.
Critical evidence should block.
Human review is required.
Synthetic data is not field data.
Software does not authorize physical action.
```
Safety Goals

The safety goals are:

prevent unsupported water-use claims
preserve uncertainty
expose missing evidence
block critical hazards
protect emergency reserves
protect critical power loads
prevent maintenance bypass
prevent infrastructure-health bypass
prevent recharge action without review
prevent synthetic examples from being mistaken for field evidence
Decision Statuses

IX-Vahdat uses conservative statuses:

allow_review
hold_for_testing
block

allow_review means the evidence can continue to human review. It does not mean the action is approved.

hold_for_testing means more evidence, service, inspection, or review is needed.

block means the current evidence should stop the dependent decision.

Risk Levels

IX-Vahdat uses:

low
moderate
high
critical

Critical risk should generally block. High risk should generally hold unless an explicit emergency human review path exists.

Water-Quality Safety

Water-quality gates should hold or block when:

required measurements are missing
measurements are stale
measurements are conflicting
sensors are failed or unverified
pathogen indicators fail
chemical screens fail
disinfection is unverified for the requested use
turbidity, conductivity, pH, or other configured thresholds fail

A water-use candidate is not final approval.

Treatment Safety

Treatment routing should not release water by itself.

A treatment route can be:

reviewable
recirculation candidate
testing hold
reject or waste-review candidate

Final use requires qualified review.

Atmospheric-Water Safety

Atmospheric-water harvesting should be treated as climate-dependent and maintenance-dependent.

The system should consider:

humidity
dew point
fog signal
wind
solar regeneration
dust risk
air quality
collection surface cleanliness
storage
treatment
energy per liter
maintenance capacity

A climate fit is not a yield guarantee.

Emergency Reserve Safety

Emergency reserve logic protects water from routine depletion.

The system should block routine release when it would breach the protected reserve.

Emergency release below reserve should only continue to explicit emergency human review, with documentation of why the breach is being considered.

Power Safety

The power model should protect:

evidence logging
water-quality sensing
minimum communications where needed
safe-hold state

Optional loads such as active condensation, nonurgent pumping, or convenience systems should shed before critical loads.

Maintenance Safety

Maintenance should block or hold when:

filters are overdue
UV systems fail
tanks are dirty or unverified
sensors are stale
pumps fail
batteries are below readiness
collection surfaces are contaminated
sorbents are unverified
mounts are unsafe

Failed critical maintenance should block dependent decisions.

Infrastructure Safety

Infrastructure-health review should hold or block for:

safety-critical leaks
corrosion
deformation
pressure anomalies
vibration
contamination pathways
unverified health states
stale observations
failed sensors

A software health state is not a structural certificate.

Managed Aquifer Recharge Safety

Managed aquifer recharge is high consequence.

The system should block or hold when:

source-water quality is not reviewed
treatment route is unreviewed
salinity risk is high
contamination risk is high
groundwater vulnerability is high
infiltration capacity is unknown or weak
geotechnical stability is weak
monitoring is unavailable
environmental review is unavailable
local authority review is unavailable
community review is unavailable
injection-well review lacks specialist approval

Software must not authorize recharge.

Evidence Safety

Receipts and bundles should preserve:

input measurements
thresholds
source IDs
evidence quality
sensor status
timestamps
reasons
required actions
reviewer status
uncertainty notes
content hashes

If evidence changes, create a new receipt or bundle.

Fail-Closed Rule

IX-Vahdat should prefer false holds over false approvals.

When in doubt:
```
hold for testing
block critical hazards
require human review
preserve evidence
do not overclaim
```
Final Rule

IX-Vahdat exists to make uncertainty visible.

Any change that hides uncertainty, weakens blockers, removes human review, or makes software sound like final authority should be rejected.
