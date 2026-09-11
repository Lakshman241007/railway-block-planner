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
      />
    </PageContainer>
  );
}
