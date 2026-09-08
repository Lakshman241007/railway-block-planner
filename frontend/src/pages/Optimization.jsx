/**
 * @file Optimization.jsx
 * @description CP-SAT Optimization Page view forwarding corridor blocks and maintenance records.
 * @module pages/Optimization
 */

import React from 'react';
import OptimizationPanel from '../components/OptimizationPanel';

export default function Optimization({
  targetDate,
  onRunOptimization,
  isOptimizing,
  optimizationResult,
  optimizationStep,
  onSelectBlock,
  blocks = [],
  maintenance = [],
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <OptimizationPanel
        targetDate={targetDate}
        onRunOptimization={onRunOptimization}
        isOptimizing={isOptimizing}
        optimizationResult={optimizationResult}
        optimizationStep={optimizationStep}
        onSelectBlock={onSelectBlock}
        blocks={blocks}
        maintenance={maintenance}
      />
    </div>
  );
}
