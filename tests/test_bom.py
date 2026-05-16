import pytest

from ix_vahdat.bom import (
    BOMCategory,
    BOMEstimate,
    BOMItem,
    DeploymentTier,
    estimate_bom,
)


def _item(**overrides: object) -> BOMItem:
    values = {
        "item_id": "ph-meter",
        "label": "portable pH meter",
        "category": BOMCategory.WATER_QUALITY,
        "quantity": 1.0,
        "unit": "each",
        "unit_cost_low": 40.0,
        "unit_cost_high": 120.0,
        "currency": "USD",
        "required": True,
        "field_replaceable": True,
        "local_substitution_allowed": True,
        "notes": "caller-supplied planning estimate only",
    }
    values.update(overrides)
    return BOMItem(**values)  # type: ignore[arg-type]


def test_bom_item_computes_extended_cost_range() -> None:
    item = _item(quantity=2.0, unit_cost_low=40.0, unit_cost_high=120.0)

    assert item.extended_cost_low == 80.0
    assert item.extended_cost_high == 240.0


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("item_id", " ", "item_id"),
        ("label", " ", "label"),
        ("unit", " ", "unit"),
        ("currency", " ", "currency"),
        ("quantity", 0.0, "quantity"),
        ("unit_cost_low", -1.0, "unit_cost_low"),
        ("unit_cost_high", -1.0, "unit_cost_high"),
        ("notes", " ", "notes"),
    ],
)
def test_bom_item_rejects_invalid_values(
    field: str,
    value: object,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _item(**{field: value})


def test_bom_item_rejects_high_cost_below_low_cost() -> None:
    with pytest.raises(ValueError, match="unit_cost_high"):
        _item(unit_cost_low=100.0, unit_cost_high=50.0)


def test_estimate_bom_totals_required_and_optional_items() -> None:
    estimate = estimate_bom(
        tier=DeploymentTier.DEMO_NODE,
        items=(
            _item(
                item_id="ph-meter",
                label="portable pH meter",
                category=BOMCategory.WATER_QUALITY,
                quantity=1.0,
                unit_cost_low=40.0,
                unit_cost_high=120.0,
                required=True,
            ),
            _item(
                item_id="solar-panel",
                label="small solar panel",
                category=BOMCategory.ENERGY,
                quantity=2.0,
                unit_cost_low=80.0,
                unit_cost_high=150.0,
                required=True,
            ),
            _item(
                item_id="fog-mesh",
                label="fog mesh test frame",
                category=BOMCategory.ATMOSPHERIC_COLLECTION,
                quantity=1.0,
                unit_cost_low=50.0,
                unit_cost_high=200.0,
                required=False,
            ),
        ),
        metadata={"synthetic_example": True},
    )

    assert estimate.tier is DeploymentTier.DEMO_NODE
    assert estimate.total_cost_low == 250.0
    assert estimate.total_cost_high == 620.0
    assert estimate.required_cost_low == 200.0
    assert estimate.required_cost_high == 420.0
    assert estimate.optional_cost_low == 50.0
    assert estimate.optional_cost_high == 200.0
    assert estimate.required_item_ids == ("ph-meter", "solar-panel")
    assert estimate.optional_item_ids == ("fog-mesh",)


def test_estimate_bom_groups_totals_by_category() -> None:
    estimate = estimate_bom(
        tier=DeploymentTier.SCHOOL_CLINIC_NODE,
        items=(
            _item(
                item_id="ph-meter",
                category=BOMCategory.WATER_QUALITY,
                unit_cost_low=40.0,
                unit_cost_high=120.0,
            ),
            _item(
                item_id="turbidity-meter",
                label="portable turbidity meter",
                category=BOMCategory.WATER_QUALITY,
                unit_cost_low=100.0,
                unit_cost_high=300.0,
            ),
            _item(
                item_id="battery",
                label="battery pack",
                category=BOMCategory.ENERGY,
                unit_cost_low=250.0,
                unit_cost_high=600.0,
            ),
        ),
    )

    totals = estimate.category_totals()

    assert totals["water_quality"] == {"low": 140.0, "high": 420.0}
    assert totals["energy"] == {"low": 250.0, "high": 600.0}


def test_estimate_bom_serializes_to_json_ready_dict() -> None:
    estimate = estimate_bom(
        tier=DeploymentTier.COMMUNITY_NODE,
        items=(_item(),),
        metadata={"review_only": True},
    )

    payload = estimate.to_dict()

    assert payload["tier"] == "community_node"
    assert payload["currency"] == "USD"
    assert payload["total_cost_low"] == 40.0
    assert payload["total_cost_high"] == 120.0
    assert payload["metadata"] == {"review_only": True}
    assert payload["items"][0]["item_id"] == "ph-meter"
    assert "not a procurement quote" in payload["non_claims"]


def test_estimate_rejects_empty_items() -> None:
    with pytest.raises(ValueError, match="at least one BOM item"):
        estimate_bom(tier=DeploymentTier.DEMO_NODE, items=())


def test_estimate_rejects_duplicate_item_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        estimate_bom(
            tier=DeploymentTier.DEMO_NODE,
            items=(_item(item_id="same"), _item(item_id="same")),
        )


def test_estimate_rejects_mixed_currencies() -> None:
    with pytest.raises(ValueError, match="estimate currency"):
        estimate_bom(
            tier=DeploymentTier.DEMO_NODE,
            currency="USD",
            items=(
                _item(item_id="usd-item", currency="USD"),
                _item(item_id="eur-item", currency="EUR"),
            ),
        )


def test_estimate_rejects_blank_assumptions_or_non_claims() -> None:
    with pytest.raises(ValueError, match="assumptions"):
        estimate_bom(
            tier=DeploymentTier.DEMO_NODE,
            items=(_item(),),
            assumptions=(" ",),
        )

    with pytest.raises(ValueError, match="non_claims"):
        estimate_bom(
            tier=DeploymentTier.DEMO_NODE,
            items=(_item(),),
            non_claims=(" ",),
        )


def test_estimate_metadata_is_immutable() -> None:
    estimate = estimate_bom(
        tier=DeploymentTier.ADVANCED_HUB,
        items=(_item(),),
        metadata={"review_only": True},
    )

    with pytest.raises(TypeError):
        estimate.metadata["review_only"] = False  # type: ignore[index]


def test_bom_estimate_direct_construction_validates_currency_match() -> None:
    with pytest.raises(ValueError, match="estimate currency"):
        BOMEstimate(
            tier=DeploymentTier.DEMO_NODE,
            items=(_item(currency="USD"),),
            currency="EUR",
            assumptions=("caller supplied costs",),
        )
