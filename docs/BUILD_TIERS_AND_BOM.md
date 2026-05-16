# IX-Vahdat Build Tiers and BOM Guidance

IX-Vahdat is a review-only humanitarian water-resilience proof-of-concept. This document describes vendor-neutral build tiers and bill-of-materials categories.

It does not provide a procurement quote, vendor recommendation, engineering approval, public-health approval, construction authorization, potable-water certification, or field-deployment authorization.

Exact prices must be refreshed with local quotes before procurement.

## Design Intent

IX-Vahdat is meant to help drought-stressed and infrastructure-stressed communities organize water evidence around:

- water-quality screening
- use-class candidate routing
- treatment review
- atmospheric-water harvesting triage
- power and energy accounting
- emergency reserve protection
- maintenance readiness
- infrastructure-health screening
- managed aquifer recharge readiness screening
- human review
- evidence receipts and evidence bundles

The system is intentionally modular. A small bench node should not pretend to be a community water system. A community node should not pretend to approve drinking water. An advanced hub should not bypass licensed review.

## Tier 1: Demo Node

### Purpose

A demo node is for bench testing, training, software validation, evidence-flow review, and safe dry-run exercises.

It should not be used for public water distribution.

### Planning Envelope

A demo node can usually fit on a workbench, folding table, or small utility cart.

Typical physical envelope:

- about the size of a small desk, rolling cart, or storage shelf
- portable by one or two people depending on batteries and tanks
- suited for dry runs, synthetic data, small non-public water samples, and software demos

### Core Functional Blocks

| Block | Vendor-Neutral Items |
| --- | --- |
| Water-quality screening | pH meter, conductivity meter, turbidity meter, thermometer, sample containers |
| Basic treatment review | sediment prefilter, cartridge filter housing, small UV module or UV review placeholder, tubing |
| Storage | small clean water container, hold container, labels for unsafe/hold/review-only water |
| Power | small solar panel or bench power supply, battery pack, fused DC distribution, meter |
| Telemetry | microcontroller or single-board computer, data logger, optional LoRa or local radio module |
| Atmospheric-water demo | small passive dew surface, fog mesh test panel, or sorbent test enclosure |
| Safety | gloves, eye protection, spill tray, labels, lockout tags |
| Evidence | run sheets, calibration records, receipt export, bundle export |

### Required Review Gates

A demo node should still require:

- non-claims acknowledgment
- sensor calibration record
- no public-use statement
- no potable-water claim
- no autonomous hardware control
- human review before any real-world interpretation

### Cost Handling

Do not hard-code costs into the repo as current prices.

Use the `BOMItem` and `estimate_bom()` model with locally refreshed quotes. The total estimate is:

```
total low estimate  = sum(quantity × local low quote)
total high estimate = sum(quantity × local high quote)
```
Include shipping, taxes, replacement consumables, testing, calibration, spare parts, and local labor separately when known.

Tier 2: School or Clinic Node
Purpose

A school or clinic node is a limited field-review concept for local water monitoring, reserve tracking, evidence capture, and controlled human-reviewed support.

It is not a certified drinking-water plant.

Planning Envelope

A school or clinic node may occupy:

a storage closet
a utility-room corner
a wheeled service cart plus storage tanks
a small sheltered outdoor pad

Typical size reference:

roughly the footprint of a large refrigerator to a small shed, depending on storage volume and power system
storage tanks dominate the space
Core Functional Blocks
Block	Vendor-Neutral Items
Water-quality screening	duplicate handheld meters, calibration fluids, sample bottles, chain-of-custody labels
Treatment review	sediment filtration, carbon filtration if appropriate, UV reactor, bypass prevention, waste hold
Storage	clean tank, unsafe/hold tank, reviewed-use tank, sealed lids, drain valves, inspection ports
Pumps and plumbing	low-pressure transfer pump, pressure gauge, flow meter, check valve, shutoff valves
Power	solar array or grid-backed supply, battery storage, charge controller, fusing, disconnects
Telemetry	local data logger, enclosure, radio or wired network, clock synchronization
Atmospheric water	fog/dew test panel or sorbent panel only where climate evidence supports review
Maintenance	spare filters, UV lamp sleeve kit, cleaning tools, pump spare, sensor spare
Safety	signage, PPE, lockout tags, spill control, electrical protection
Evidence	site logbook, reviewer signoff, JSON receipts, evidence bundle export
Required Review Gates

A school or clinic node should hold or block when:

water-quality evidence is missing, stale, or conflicting
pathogen or chemical evidence fails
treatment path is unreviewed
emergency reserve would be breached by routine use
safe-hold power loads cannot be protected
storage cleanliness or tank integrity is unverified
maintenance is overdue
human review is missing
Cost Handling

Use locally refreshed quotes. At this tier, the major cost drivers are usually:

storage volume
treatment hardware
batteries
solar or backup power
meters and lab testing
enclosure and weather protection
installation labor
local compliance review

IX-Vahdat should report cost ranges, not single-point certainty.

Tier 3: Community Node
Purpose

A community node is a larger local water-resilience review concept. It may combine monitoring, treatment review, reserve protection, distribution staging, atmospheric-water triage, and reuse/recharge planning.

It must remain under qualified human control.

Planning Envelope

A community node may require:

a small utility building
shipping-container-sized equipment space
outdoor tank pad
solar canopy or roof space
separate clean/hold/waste areas

Typical size reference:

one small shipping-container-scale equipment room plus tank area
total footprint can range from a small parking area to a small courtyard depending on storage and solar area
Core Functional Blocks
Block	Vendor-Neutral Items
Intake review	screened intake, turbidity monitoring, source labeling, sample ports
Treatment review	modular filtration skid, UV or disinfection review path, recirculation loop, waste hold
Storage	multiple labeled tanks, reserve tank, reviewed-use tank, hold tank, inspection plan
Pumping	duty pump, backup pump, pressure and flow monitoring, valves, leak detection
Power	solar, battery, grid or generator input where legal, load shedding, critical-load protection
Telemetry	site gateway, local dashboard, offline logs, tamper-evident evidence exports
Atmospheric water	fog/dew/sorbent/active-condensation pilots only if climate and energy support review
Reuse	greywater or reclaimed-water review only under local public-health requirements
MAR screening	monitoring-only or pilot-readiness screen; no recharge without legal and specialist review
Maintenance	scheduled spares, consumables, calibration plan, cleaning plan, operator checklists
Safety	lockout, signage, electrical review, confined-space caution where applicable
Evidence	receipts, bundles, runbooks, reviewer records, maintenance logs
Required Review Gates

A community node should block or hold for:

unsafe-hold water
critical infrastructure leak
active critical failure mode
failed critical maintenance item
critical reserve breach
missing local authority review
missing public-health review
missing environmental review where recharge/discharge is involved
missing human reviewer identity
unknown or unmeasured energy boundary
Cost Handling

Community-node costs are site-specific. Do not publish a false universal cost.

Use the BOM estimator with local quotes and separate totals for:

required core system
optional atmospheric-water modules
optional recharge monitoring modules
required maintenance spares
required testing and calibration
installation and local approval costs
contingency
Tier 4: Advanced Hub
Purpose

An advanced hub is a multi-path resilience site for research-grade evidence handling, multiple water-support paths, redundant power, stronger telemetry, and expanded monitoring.

It is not automatically a public utility.

Planning Envelope

An advanced hub may require:

dedicated site pad
equipment container or small building
tank farm
solar canopy or adjacent solar area
protected lab/sample area
fenced maintenance and storage zone

Typical size reference:

small utility-site scale rather than single-room scale
often larger than a shipping container once tanks, solar, access space, and service clearance are included
Core Functional Blocks
Block	Vendor-Neutral Items
Multi-source intake	reviewed sources, sample ports, isolation valves, source labeling
Treatment review	redundant filtration, disinfection validation path, recirculation, reject/hold routing
Water-quality lab support	meters, calibration kits, sample refrigeration if needed, lab chain-of-custody process
Atmospheric-water stack	fog, dew, sorbent, solar-desorption, or active-condensation pilots where evidence supports
Energy stack	solar, storage, load control, critical-load protection, metering, backup input
Infrastructure monitoring	tank, pipe, pump, valve, mount, panel, and drain health observations
MAR monitoring	groundwater observation, source-water screening, environmental and authority review tracking
Emergency reserve	protected reserve, emergency review records, no routine breach logic
Evidence and audit	signed-style receipts, deterministic bundles, exported runbooks, reviewer signoffs
Maintenance	scheduled service, parts inventory, calibration, cleaning, spare sensors and pumps
Required Review Gates

An advanced hub requires the strongest boundary language:

no autonomous water release
no autonomous recharge
no autonomous treatment decision
no potable-water claim from software alone
no discharge approval from software alone
no public distribution without public-health authority
no construction without qualified engineering and permitting
no emergency reserve breach without explicit emergency review
Cost Handling

Advanced hubs should not use generic cost promises.

Costs must be decomposed into:

civil works
tanks
treatment modules
atmospheric-water modules
electrical and storage
telemetry and evidence systems
laboratory testing
maintenance spares
installation labor
local approval
contingency
Recommended BOM Categories

The code-level BOM model supports these categories:

water_quality
treatment
atmospheric_collection
storage
energy
power_electronics
pumping
telemetry
structure
safety
maintenance
consumables
lab_review
other
Minimum Practical BOM Checklist

A serious IX-Vahdat node should account for the following before field review.

Measurement and Evidence
pH measurement
conductivity or salinity measurement
turbidity measurement
temperature measurement
pathogen testing path
chemical screening path
calibration supplies
sample containers
chain-of-custody labels
local data logger
evidence export method
Treatment and Routing
prefilter
primary filter
disinfection review path
recirculation path
reject/hold path
sample ports
flow meter
pressure gauge
labeled valves
physical lockout or tagout process
Storage
clean/review tank
unsafe/hold tank
emergency reserve tank or reserve partition
tank lids
drain valves
inspection access
cleaning supplies
contamination-prevention labels
Energy and Power
measured power source
battery or reserve power where needed
charge controller if solar is used
fuse or breaker protection
disconnect
power meter
critical-load plan
safe-hold load list
Atmospheric Water Modules

Use only where climate evidence supports review.

Possible modules:

fog mesh
radiative dew surface
sorbent cartridge test module
solar desorption enclosure
hydrogel/salt research cartridge where material safety is reviewed
active condensation module where power budget supports review

Collected water still requires treatment and quality review.

Infrastructure Monitoring
tank inspection record
pipe inspection record
pump inspection record
panel or mesh mount inspection
leak observation
corrosion observation
pressure anomaly observation
vibration observation
contamination pathway observation
Safety and Maintenance
PPE
spill tray
labels
lockout tags
filter spares
UV spares if used
pump spare or repair kit
sensor spare
cleaning kit
maintenance log
What Not to Do

Do not use IX-Vahdat BOM guidance to:

buy parts without local review
represent example costs as current market prices
skip public-health testing
skip electrical safety review
skip environmental review
scale a demo node into a public water system
claim a water source is potable because a software gate passed
use atmospheric-water modules as a guaranteed water source
perform managed aquifer recharge without specialist approval
Final Rule

A BOM is not a system.

A system requires measurement, installation, maintenance, testing, review, local approval, and continuous evidence.
