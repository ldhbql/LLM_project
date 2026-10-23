"""Pydantic models mirroring the upstream ``Pet`` payload.

Field names follow the upstream camelCase wire format via aliases; the Python
attributes stay snake_case. ``extra="allow"`` keeps any field the upstream adds
without breaking this MVP.

These models drive both validation of the upstream response and the tool's
``outputSchema`` (see ``tools/list_pets.py``).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Base(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")


def _none_to_list(value: object) -> object:
    return [] if value is None else value


class MedicalRecord(_Base):
    id: str | None = None
    visit_date: str | None = Field(default=None, alias="visitDate")
    doctor: str | None = None
    diagnosis: str | None = None
    symptoms: str | None = None
    treatment: str | None = None
    prescription: list[str] = Field(default_factory=list)
    weight_kg: float | None = Field(default=None, alias="weightKg")
    temperature: float | None = None
    follow_up: str | None = Field(default=None, alias="followUp")
    charge: float | None = None
    created_at: str | None = Field(default=None, alias="createdAt")

    @field_validator("prescription", mode="before")
    @classmethod
    def _coerce_prescription(cls, value: object) -> object:
        return _none_to_list(value)


class Charge(_Base):
    id: str | None = None
    item: str | None = None
    category: str | None = None
    amount: float | None = None
    doctor: str | None = None
    date: str | None = None


class Pet(_Base):
    id: str
    name: str | None = None
    species: str | None = None
    breed: str | None = None
    gender: str | None = None
    age_months: int | None = Field(default=None, alias="ageMonths")
    color: str | None = None
    chip_no: str | None = Field(default=None, alias="chipNo")
    owner_name: str | None = Field(default=None, alias="ownerName")
    owner_phone: str | None = Field(default=None, alias="ownerPhone")
    owner_addr: str | None = Field(default=None, alias="ownerAddr")
    doctor: str | None = None
    disease: str | None = None
    status: str | None = None
    allergy: str | None = None
    note: str | None = None
    records: list[MedicalRecord] = Field(default_factory=list)
    charges: list[Charge] = Field(default_factory=list)
    total_cost: float | None = Field(default=None, alias="totalCost")
    visit_count: int | None = Field(default=None, alias="visitCount")
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")

    @field_validator("records", "charges", mode="before")
    @classmethod
    def _coerce_lists(cls, value: object) -> object:
        # The create endpoint returns null for a brand-new pet's empty lists.
        return _none_to_list(value)


class ListPetsOutput(_Base):
    """The ``data`` object returned by ``GET /api/v1/pets``."""

    items: list[Pet] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = Field(default=20, alias="pageSize")
    total_pages: int = Field(default=0, alias="totalPages")
    total_cost: float = Field(default=0.0, alias="totalCost")
