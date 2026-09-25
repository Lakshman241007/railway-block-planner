# Maintenance Prioritization Engine

The maintenance prioritization engine calculates a deterministic priority
value for railway maintenance work.

## Flow

MaintenanceWork
    ↓
Priority Factor Calculation
    ↓
Five normalized factors
    ↓
Configurable weighted scoring
    ↓
PriorityInformation

## Priority Factors

All factors are normalized to a range of 0–100.

### 1. Urgency

Represents how urgently the maintenance work should be addressed based
on maintenance status and whether maintenance is required.

### 2. Criticality

Maps the maintenance priority level to a normalized value:

- Low → 25
- Medium → 50
- High → 75
- Critical → 100

### 3. Overdue Factor

Increases as the requested maintenance date becomes overdue.

The factor reaches 100 after 30 overdue days.

### 4. Asset Availability Impact

Represents the impact of maintenance duration on asset availability.

Eight hours or more is treated as maximum impact.

### 5. Operational Impact

Combines the number of required resources and whether maintenance is
required.

## Weighted Scoring

The final priority value is calculated using configurable weights:

```text
Priority Value =
    W1 × Urgency
  + W2 × Criticality
  + W3 × Overdue Factor
  + W4 × Asset Availability Impact
  + W5 × Operational Impact