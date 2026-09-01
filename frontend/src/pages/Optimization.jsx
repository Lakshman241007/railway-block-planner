import React from 'react';
import OptimizationPanel from '../components/OptimizationPanel';

export default function Optimization({
  targetDate,
  onRunOptimization,
  isOptimizing,
  optimizationResult,
  optimizationStep,
  onSelectBlock,
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
      />
    </div>
  );
}
