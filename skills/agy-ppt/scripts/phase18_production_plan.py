#!/usr/bin/env python3
"""Phase 18.2 deterministic element-level production planning."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from phase18_contract import (
    CropBehavior,
    DeliveryEditabilityContract,
    DeliveryProfile,
    EditabilityClass,
    EditabilityEnvelope,
    FontPortability,
    OverflowBehavior,
    ProductionStrategy,
    ReplacementMode,
    ReplacementSemantics,
    ShrinkPolicy,
)


ERROR_PRODUCTION_PLAN_INVALID = "PHASE18_PRODUCTION_PLAN_INVALID"


class ProductionPlanError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class ElementRole(str, Enum):
    NAME = "NAME"
    JOB_TITLE = "JOB_TITLE"
    DATE = "DATE"
    PRICE = "PRICE"
    KPI = "KPI"
    CONTACT = "CONTACT"
    CTA = "CTA"
    TITLE = "TITLE"
    BODY = "BODY"
    TABLE = "TABLE"
    LOGO = "LOGO"
    PHOTO = "PHOTO"
    SIMPLE_SHAPE = "SIMPLE_SHAPE"
    ARTISTIC_HEADLINE = "ARTISTIC_HEADLINE"
    HERO_ARTWORK = "HERO_ARTWORK"
    CHART = "CHART"
    DECORATIVE_ARTWORK = "DECORATIVE_ARTWORK"


class PortabilityRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


_REQUIRED_TEXT = frozenset({
    ElementRole.NAME, ElementRole.JOB_TITLE, ElementRole.DATE, ElementRole.PRICE,
    ElementRole.KPI, ElementRole.CONTACT, ElementRole.CTA,
})
_TEXT = _REQUIRED_TEXT | frozenset({ElementRole.TITLE, ElementRole.BODY, ElementRole.TABLE})


def _clean(value: str, label: str) -> str:
    result = value.strip() if isinstance(value, str) else ""
    if not result:
        raise ProductionPlanError(ERROR_PRODUCTION_PLAN_INVALID, f"{label} is required")
    return result


@dataclass(frozen=True)
class ElementPlanningInput:
    element_id: str
    semantic_ref: str
    narrative_ref: str
    role: ElementRole
    approved_content: str
    font_portability: FontPortability = FontPortability.FONT_SAFE
    evidence_claim_ids: tuple[str, ...] = ()
    vector_safe: bool = False
    structured_data: bool = False

    def __post_init__(self) -> None:
        for name in ("element_id", "semantic_ref", "narrative_ref", "approved_content"):
            object.__setattr__(self, name, _clean(getattr(self, name), name))
        if not isinstance(self.role, ElementRole) or not isinstance(self.font_portability, FontPortability):
            raise ProductionPlanError(ERROR_PRODUCTION_PLAN_INVALID, "element role or font portability is invalid")
        if not isinstance(self.vector_safe, bool) or not isinstance(self.structured_data, bool):
            raise ProductionPlanError(ERROR_PRODUCTION_PLAN_INVALID, "planning flags must be boolean")
        claims = tuple(_clean(item, "evidence claim id") for item in self.evidence_claim_ids)
        if len(claims) != len(set(claims)):
            raise ProductionPlanError(ERROR_PRODUCTION_PLAN_INVALID, "evidence claim ids must be unique")
        object.__setattr__(self, "evidence_claim_ids", tuple(sorted(claims)))


@dataclass(frozen=True)
class ElementProductionPlan:
    plan_id: str
    element_id: str
    semantic_ref: str
    narrative_ref: str
    approved_content: str
    evidence_claim_ids: tuple[str, ...]
    role: ElementRole
    portability_risk: PortabilityRisk
    contract: DeliveryEditabilityContract

    def internal_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "element_id": self.element_id,
            "semantic_ref": self.semantic_ref,
            "narrative_ref": self.narrative_ref,
            "approved_content": self.approved_content,
            "evidence_claim_ids": list(self.evidence_claim_ids),
            "role": self.role.value,
            "portability_risk": self.portability_risk.value,
            "contract": self.contract.internal_dict(),
        }

    def canonical_json(self) -> str:
        return json.dumps(self.internal_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _text_contract(item: ElementPlanningInput, profile: DeliveryProfile) -> tuple[DeliveryEditabilityContract, PortabilityRisk]:
    required = item.role in _REQUIRED_TEXT
    if item.font_portability is FontPortability.FONT_CRITICAL:
        editability = EditabilityClass.LOCKED_REQUIRED if item.role is ElementRole.ARTISTIC_HEADLINE else EditabilityClass.LOCKED_PREFERRED
        return DeliveryEditabilityContract(
            editability, ProductionStrategy.LOCKED_VISUAL, item.font_portability,
            delivery_profile=profile,
        ), PortabilityRisk.HIGH
    max_chars = 36 if item.role in {ElementRole.TITLE, ElementRole.NAME, ElementRole.JOB_TITLE} else 180
    envelope = EditabilityEnvelope(
        expected_min_characters=1,
        expected_max_characters=max_chars,
        expected_min_lines=1,
        expected_max_lines=2 if max_chars == 36 else 8,
        minimum_font_size=14 if max_chars == 36 else 10,
        maximum_font_size=40 if max_chars == 36 else 24,
        shrink_policy=ShrinkPolicy.TO_MINIMUM,
        overflow_behavior=OverflowBehavior.FLAG_FOR_REVIEW,
        layout_tolerance_points=2.0,
    )
    return DeliveryEditabilityContract(
        EditabilityClass.EDITABLE_REQUIRED if required else EditabilityClass.EDITABLE_PREFERRED,
        ProductionStrategy.NATIVE_TEXT,
        item.font_portability,
        envelope=envelope,
        delivery_profile=profile,
    ), PortabilityRisk.LOW if item.font_portability is FontPortability.FONT_SAFE else PortabilityRisk.MEDIUM


def _replacement_contract(
    item: ElementPlanningInput,
    profile: DeliveryProfile,
    strategy: ProductionStrategy,
) -> DeliveryEditabilityContract:
    return DeliveryEditabilityContract(
        EditabilityClass.REPLACEABLE,
        strategy,
        item.font_portability,
        envelope=EditabilityEnvelope(
            replacement_min_aspect_ratio=0.5,
            replacement_max_aspect_ratio=2.5,
            crop_behavior=CropBehavior.PRESERVE_CROP if item.role is ElementRole.PHOTO else CropBehavior.PRESERVE_FRAME,
            layout_tolerance_points=1.0,
        ),
        replacement=ReplacementSemantics(
            ReplacementMode.PRESERVE_CROP if item.role is ElementRole.PHOTO else ReplacementMode.PRESERVE_FRAME
        ),
        delivery_profile=profile,
    )


def plan_element(item: ElementPlanningInput, profile: DeliveryProfile = DeliveryProfile.BALANCED) -> ElementProductionPlan:
    """Apply categorical policy; never alter approved content or semantic identities."""
    if not isinstance(item, ElementPlanningInput) or not isinstance(profile, DeliveryProfile):
        raise ProductionPlanError(ERROR_PRODUCTION_PLAN_INVALID, "element and delivery profile are required")
    if item.role in _TEXT:
        contract, risk = _text_contract(item, profile)
    elif item.role is ElementRole.ARTISTIC_HEADLINE:
        contract = DeliveryEditabilityContract(
            EditabilityClass.LOCKED_REQUIRED,
            ProductionStrategy.LOCKED_VISUAL,
            FontPortability.FONT_CRITICAL,
            delivery_profile=profile,
        )
        risk = PortabilityRisk.HIGH
    elif item.role in {ElementRole.LOGO, ElementRole.PHOTO}:
        strategy = ProductionStrategy.VECTOR_GRAPHIC if item.role is ElementRole.LOGO and item.vector_safe else ProductionStrategy.NATIVE_IMAGE
        contract = _replacement_contract(item, profile, strategy)
        risk = PortabilityRisk.LOW if strategy is ProductionStrategy.NATIVE_IMAGE else PortabilityRisk.MEDIUM
    elif item.role is ElementRole.SIMPLE_SHAPE:
        contract = DeliveryEditabilityContract(
            EditabilityClass.EDITABLE_PREFERRED,
            ProductionStrategy.NATIVE_SHAPE,
            item.font_portability,
            delivery_profile=profile,
        )
        risk = PortabilityRisk.LOW
    elif item.role is ElementRole.CHART:
        if item.structured_data:
            contract = DeliveryEditabilityContract(
                EditabilityClass.EDITABLE_PREFERRED,
                ProductionStrategy.NATIVE_CHART,
                item.font_portability,
                delivery_profile=profile,
            )
            risk = PortabilityRisk.MEDIUM
        else:
            contract = DeliveryEditabilityContract(
                EditabilityClass.LOCKED_PREFERRED,
                ProductionStrategy.RASTER_REGION,
                item.font_portability,
                delivery_profile=profile,
            )
            risk = PortabilityRisk.LOW
    else:
        if item.vector_safe and profile is DeliveryProfile.EDITABILITY_PRIORITY and item.role is ElementRole.DECORATIVE_ARTWORK:
            contract = DeliveryEditabilityContract(
                EditabilityClass.EDITABLE_PREFERRED,
                ProductionStrategy.VECTOR_GRAPHIC,
                item.font_portability,
                delivery_profile=profile,
            )
            risk = PortabilityRisk.MEDIUM
        else:
            contract = DeliveryEditabilityContract(
                EditabilityClass.LOCKED_REQUIRED if item.role is ElementRole.HERO_ARTWORK else EditabilityClass.LOCKED_PREFERRED,
                ProductionStrategy.LOCKED_VISUAL if profile is DeliveryProfile.FIDELITY else ProductionStrategy.RASTER_REGION,
                item.font_portability,
                delivery_profile=profile,
            )
            risk = PortabilityRisk.LOW
    payload = {
        "element_id": item.element_id,
        "semantic_ref": item.semantic_ref,
        "narrative_ref": item.narrative_ref,
        "approved_content": item.approved_content,
        "evidence_claim_ids": list(item.evidence_claim_ids),
        "role": item.role.value,
        "portability_risk": risk.value,
        "contract": contract.internal_dict(),
    }
    plan_id = "ep:" + hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()[:16]
    return ElementProductionPlan(
        plan_id, item.element_id, item.semantic_ref, item.narrative_ref, item.approved_content,
        item.evidence_claim_ids, item.role, risk, contract,
    )


def plan_elements(
    elements: Iterable[ElementPlanningInput],
    profile: DeliveryProfile = DeliveryProfile.BALANCED,
) -> tuple[ElementProductionPlan, ...]:
    clean = tuple(elements)
    if not clean or any(not isinstance(item, ElementPlanningInput) for item in clean):
        raise ProductionPlanError(ERROR_PRODUCTION_PLAN_INVALID, "elements are required")
    if len({item.element_id for item in clean}) != len(clean):
        raise ProductionPlanError(ERROR_PRODUCTION_PLAN_INVALID, "element ids must be unique")
    return tuple(plan_element(item, profile) for item in clean)


__all__ = [
    "ERROR_PRODUCTION_PLAN_INVALID", "ElementPlanningInput", "ElementProductionPlan",
    "ElementRole", "PortabilityRisk", "ProductionPlanError", "plan_element", "plan_elements",
]
