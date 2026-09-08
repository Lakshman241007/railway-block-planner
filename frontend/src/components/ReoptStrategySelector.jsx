/**
 * @file ReoptStrategySelector.jsx
 * @description Strategy Preset Selector for CP-SAT Multi-Objective Re-Optimization.
 * Allows operators to select trade-offs: Balanced, Max Throughput, Minimal Churn, Safety First.
 * @module components/ReoptStrategySelector
 */

import React from 'react';

const STRATEGIES = [
  {
    id: 'balanced',
    icon: '⚖️',
    name: 'Balanced',
    desc: 'Standard multi-objective balance between priority, throughput & disruption',
  },
  {
    id: 'max_throughput',
    icon: '📈',
    name: 'Max Throughput',
    desc: 'Accommodate maximum possessions; relaxed deviation penalty',
  },
  {
    id: 'minimal_disruption',
    icon: '📌',
    name: 'Minimal Churn',
    desc: 'Strictly protect existing windows; heavy schedule shift penalty',
  },
  {
    id: 'safety_priority',
    icon: '🦺',
    name: 'Safety First',
    desc: 'Enforce extended >=20 min buffer spacing around passenger traffic',
  },
];

export default function ReoptStrategySelector({ strategy, onSelectStrategy, disabled }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
      <label className="detail-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span>🎯 Re-Optimization Solver Strategy Preset</span>
      </label>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
        {STRATEGIES.map((s) => {
          const isSelected = strategy === s.id;
          return (
            <button
              key={s.id}
              type="button"
              disabled={disabled}
              onClick={() => onSelectStrategy(s.id)}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
                textAlign: 'left',
                gap: 4,
                padding: '10px 14px',
                borderRadius: '8px',
                border: isSelected ? '1px solid #00f0ff' : '1px solid rgba(255, 255, 255, 0.1)',
                background: isSelected ? 'rgba(0, 240, 255, 0.12)' : 'rgba(15, 23, 42, 0.6)',
                color: isSelected ? '#ffffff' : '#94a3b8',
                cursor: disabled ? 'not-allowed' : 'pointer',
                transition: 'all 0.2s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, fontSize: '0.9rem', color: isSelected ? '#00f0ff' : '#f8fafc' }}>
                <span>{s.icon}</span>
                <span>{s.name}</span>
                {isSelected && <span style={{ fontSize: '0.7rem', color: '#00f0ff', marginLeft: 'auto' }}>● ACTIVE</span>}
              </div>
              <div style={{ fontSize: '0.74rem', lineHeight: 1.3, color: '#94a3b8' }}>
                {s.desc}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
