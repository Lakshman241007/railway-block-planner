/**
 * @file Optimization.jsx
 * @description CP-SAT Optimization Page view forwarding corridor blocks and maintenance records.
 * @module pages/Optimization
 */

import React from 'react';
import PageContainer from '../components/PageContainer';
import OptimizationPanel from '../components/OptimizationPanel';

export default function Optimization({
  targetDate,
  onRunOptimization,
  onResetBaseline,
  isOptimizing,
  optimizationResult,
  optimizationStep,
  onSelectBlock,
  blocks = [],
  maintenance = [],
}) {
  return (
    <PageContainer>
      <OptimizationPanel
        targetDate={targetDate}
        onRunOptimization={onRunOptimization}
        onResetBaseline={onResetBaseline}
        isOptimizing={isOptimizing}
        optimizationResult={optimizationResult}
        optimizationStep={optimizationStep}
        onSelectBlock={onSelectBlock}
        blocks={blocks}
        maintenance={maintenance}
      />
    </PageContainer>
  );
}
