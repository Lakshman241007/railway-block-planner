"""
Schemas for the AI maintenance prioritization engine.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PriorityFactors(BaseModel):
    """Normalized 0-100 factors used to calculate maintenance priority."""

    urgency: float = Field(ge=0, le=100)
    criticality: float = Field(ge=0, le=100)
    overdue_factor: float = Field(ge=0, le=100)
    asset_availability_impact: float = Field(ge=0, le=100)
    operational_impact: float = Field(ge=0, le=100)


class PriorityWeights(BaseModel):
    """Configurable weights for the five prioritization factors."""

    urgency: float = Field(default=0.20, ge=0)
    criticality: float = Field(default=0.25, ge=0)
    overdue_factor: float = Field(default=0.20, ge=0)
    asset_availability_impact: float = Field(default=0.15, ge=0)
    operational_impact: float = Field(default=0.20, ge=0)


class PriorityInformation(BaseModel):
    """AI-generated prioritization result for a maintenance record."""

    maintenance_id: str = Field(min_length=1)
    factors: PriorityFactors
    priority_value: float = Field(ge=0, le=100)
    explanation: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)