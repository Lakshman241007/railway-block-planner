/**
 * @file OptimizationPanel.jsx
 * @description CP-SAT Optimization and Re-Optimization Preferences Control Panel.
 * Composes Strategy Presets, Pre-run Task Preferences, Reopt Delta Telemetry, and Results Tables.
 * @module components/OptimizationPanel
 */

import React, { useState } from 'react';
import OptimizationHeaderControl from './OptimizationHeaderControl';
import ReoptStrategySelector from './ReoptStrategySelector';
import TaskPreferencesTable from './TaskPreferencesTable';
import ReoptDeltaCard from './ReoptDeltaCard';
import ScheduledPossessionsTable from './ScheduledPossessionsTable';
import UnscheduledDiagnosticsTable from './UnscheduledDiagnosticsTable';
import { useCandidateTasks } from './useCandidateTasks';


export default function OptimizationPanel({
  targetDate,
  onRunOptimization,
  isOptimizing,
  optimizationResult,
  optimizationStep = 0,
  onSelectBlock,
  blocks = [],
  maintenance = [],
}) {
  const [horizonDays, setHorizonDays] = useState(7);
  const [includeForecast, setIncludeForecast] = useState(true);
  const [bufferMinutes, setBufferMinutes] = useState(15);
  const [strategy, setStrategy] = useState('balanced');
  const [priorityOverrides, setPriorityOverrides] = useState({});
  const [taskModes, setTaskModes] = useState({});
  const [pinnedSlots, setPinnedSlots] = useState({});
  const [isPreferencesOpen, setIsPreferencesOpen] = useState(true);

  const candidateTasks = useCandidateTasks(maintenance, blocks, optimizationResult);

  const handleRun = () => {
    const pinned = {};
    const mandatory = [];
    const excluded = [];

    Object.entries(taskModes).forEach(([id, mode]) => {
      if (mode === 'pin') {
        const found = candidateTasks.find((t) => t.id === id);
        pinned[id] = pinnedSlots[id] || found?.defaultSlot || '02:00-04:00';
      } else if (mode === 'force') mandatory.push(id);
      else if (mode === 'skip') excluded.push(id);
    });

    const activeOverrides = {};
    Object.entries(priorityOverrides).forEach(([id, p]) => {
      if (p) activeOverrides[id] = p;
    });

    if (onRunOptimization) {
      onRunOptimization({
        target_date: targetDate,
        horizon_days: parseInt(horizonDays, 10),
        include_forecast: includeForecast,
        buffer_minutes: parseInt(bufferMinutes, 10),
        strategy_preset: strategy,
        priority_overrides: Object.keys(activeOverrides).length ? activeOverrides : null,
        pinned_slots: Object.keys(pinned).length ? pinned : null,
        mandatory_request_ids: mandatory.length ? mandatory : null,
        exclude_from_reopt: excluded.length ? excluded : null,
      });
    }
  };

  const scheduledBlocks = optimizationResult?.scheduled_blocks || [];
  const unscheduledBlocks = optimizationResult?.unscheduled_blocks || [];
  const stats = optimizationResult?.solver_statistics;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <OptimizationHeaderControl
        horizonDays={horizonDays}
        setHorizonDays={setHorizonDays}
        bufferMinutes={bufferMinutes}
        setBufferMinutes={setBufferMinutes}
        includeForecast={includeForecast}
        setIncludeForecast={setIncludeForecast}
        handleRun={handleRun}
        isOptimizing={isOptimizing}
        optimizationStep={optimizationStep}
      />

      <ReoptStrategySelector
        strategy={strategy}
        onSelectStrategy={setStrategy}
        disabled={isOptimizing}
      />

      <TaskPreferencesTable
        candidateTasks={candidateTasks}
        priorityOverrides={priorityOverrides}
        onOverridePriority={(id, p) => setPriorityOverrides((prev) => ({ ...prev, [id]: p }))}
        taskModes={taskModes}
        onSelectMode={(id, m) => setTaskModes((prev) => ({ ...prev, [id]: m }))}
        pinnedSlots={pinnedSlots}
        onUpdatePinnedSlot={(id, s) => setPinnedSlots((prev) => ({ ...prev, [id]: s }))}
        isOpen={isPreferencesOpen}
        onToggleOpen={() => setIsPreferencesOpen(!isPreferencesOpen)}
      />

      {stats && <ReoptDeltaCard stats={stats} totalScheduled={scheduledBlocks.length} />}
      <UnscheduledDiagnosticsTable blocks={unscheduledBlocks} onSelectBlock={onSelectBlock} />
      <ScheduledPossessionsTable blocks={scheduledBlocks} onSelectBlock={onSelectBlock} />
    </div>
  );
}
