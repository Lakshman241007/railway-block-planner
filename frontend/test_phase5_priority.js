/**
 * @file test_phase5_priority.js
 * @description Frontend Unit Tests for Phase 5 — Operator UI: Priority + Explainability.
 * Tests extractPriorityEnrichment, PriorityBadge value presentation, factor extraction,
 * AI explanation handling, and empty/missing state resilience.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { extractPriorityEnrichment, getPriorityClass } from './src/types/index.js';

test('TEST 1: Priority value extracts correctly and unchanged', () => {
  const recordWithDirectValue = {
    priority: 'Critical',
    priority_value: 94.5,
  };
  const res1 = extractPriorityEnrichment(recordWithDirectValue);
  assert.equal(res1.priorityValue, 94.5);
  assert.equal(res1.hasPriorityData, true);

  const recordWithEnrichedValue = {
    priority: 'High',
    priority_enrichment: {
      priority_value: 88,
      urgency: 0.85,
    },
  };
  const res2 = extractPriorityEnrichment(recordWithEnrichedValue);
  assert.equal(res2.priorityValue, 88);
  assert.equal(res2.urgency, 0.85);
});

test('TEST 2: Priority factors extract correctly from priority_enrichment', () => {
  const fullEnrichedRecord = {
    priority_enrichment: {
      priority_value: 92,
      urgency: 0.91,
      criticality: 0.88,
      overdue_factor: 1.20,
      asset_availability_impact: 0.84,
      operational_impact: 0.76,
    },
  };
  const factors = extractPriorityEnrichment(fullEnrichedRecord);
  assert.equal(factors.priorityValue, 92);
  assert.equal(factors.urgency, 0.91);
  assert.equal(factors.criticality, 0.88);
  assert.equal(factors.overdueFactor, 1.20);
  assert.equal(factors.assetAvailabilityImpact, 0.84);
  assert.equal(factors.operationalImpact, 0.76);
});

test('TEST 3: AI explanation extracts correctly from all standard locations', () => {
  const rec1 = {
    priority_enrichment: {
      explanation: 'High urgency and asset criticality increased the maintenance priority.',
    },
  };
  assert.equal(
    extractPriorityEnrichment(rec1).explanation,
    'High urgency and asset criticality increased the maintenance priority.'
  );

  const rec2 = {
    priority_enrichment: {
      metadata: {
        ai_explanation: 'Overdue renewal requires immediate track slot allocation.',
      },
    },
  };
  assert.equal(
    extractPriorityEnrichment(rec2).explanation,
    'Overdue renewal requires immediate track slot allocation.'
  );

  const rec3 = {
    ai_explanation: 'Direct explanation on block record.',
  };
  assert.equal(
    extractPriorityEnrichment(rec3).explanation,
    'Direct explanation on block record.'
  );
});

test('TEST 4: Missing optional factors do not break extractor (returns null, not fake values)', () => {
  const partialRecord = {
    priority: 'Medium',
    priority_enrichment: {
      priority_value: 70,
      urgency: 0.65,
    },
  };
  const res = extractPriorityEnrichment(partialRecord);
  assert.equal(res.priorityValue, 70);
  assert.equal(res.urgency, 0.65);
  assert.equal(res.criticality, null);
  assert.equal(res.overdueFactor, null);
  assert.equal(res.assetAvailabilityImpact, null);
  assert.equal(res.operationalImpact, null);
  assert.equal(res.explanation, null);
});

test('TEST 5: Missing priority data returns clean empty state without throwing', () => {
  const emptyRecord = {
    block_id: 'BLK-001',
    location: 'Chennai-Arakkonam',
  };
  const res = extractPriorityEnrichment(emptyRecord);
  assert.equal(res.hasPriorityData, false);
  assert.equal(res.priorityValue, null);
  assert.equal(res.urgency, null);
  assert.equal(res.explanation, null);

  const nullRes = extractPriorityEnrichment(null);
  assert.equal(nullRes.hasPriorityData, false);
  assert.equal(nullRes.priorityValue, null);
});

test('TEST 6: Zero values (0) are preserved and NOT treated as null or missing', () => {
  const zeroRecord = {
    priority_value: 0,
    priority_enrichment: {
      urgency: 0,
      criticality: 0,
    },
  };
  const res = extractPriorityEnrichment(zeroRecord);
  assert.equal(res.priorityValue, 0);
  assert.equal(res.urgency, 0);
  assert.equal(res.criticality, 0);
  assert.equal(res.hasPriorityData, true);
});

test('TEST 7: Priority CSS class mappings remain stable', () => {
  assert.equal(getPriorityClass('Critical'), 'badge-critical');
  assert.equal(getPriorityClass('High'), 'badge-high');
  assert.equal(getPriorityClass('Medium'), 'badge-medium');
  assert.equal(getPriorityClass('Low'), 'badge-low');
  assert.equal(getPriorityClass('unknown'), 'badge-low');
});

test('TEST 8: Priority value is never mutated or scaled by the frontend', () => {
  const exactBackendScores = [92, 100, 45.2, 0, 999];
  exactBackendScores.forEach((score) => {
    const extracted = extractPriorityEnrichment({ priority_value: score }).priorityValue;
    assert.equal(extracted, score, `Score ${score} was mutated to ${extracted}`);
  });
});
