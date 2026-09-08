import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import BlockDetailModal from './components/BlockDetailModal';
import Toast from './components/Toast';

import Dashboard from './pages/Dashboard';
import Schedule from './pages/Schedule';
import Optimization from './pages/Optimization';
import Blocks from './pages/Blocks';
import Maintenance from './pages/Maintenance';
import Trains from './pages/Trains';
import Forecast from './pages/Forecast';
import Conflicts from './pages/Conflicts';

import { checkBackendHealth } from './services/api';
import { getBlocks } from './services/blocks';
import { getMaintenance } from './services/maintenance';
import { getTrains } from './services/trains';
import { getMovements } from './services/movements';
import { getTimetable } from './services/timetable';
import { getGoodsForecast, runGoodsForecast } from './services/forecast';
import { detectConflicts } from './services/scheduler';
import { optimizePlan, getLatestOptimizedPlan } from './services/plans';

export default function App() {
  const [activePage, setActivePage] = useState('dashboard');
  const [targetDate, setTargetDate] = useState('2026-09-07');
  const [isOnline, setIsOnline] = useState(true);
  const [loading, setLoading] = useState(false);

  // Core Railway Data State
  const [blocks, setBlocks] = useState([]);
  const [maintenance, setMaintenance] = useState([]);
  const [trains, setTrains] = useState([]);
  const [movements, setMovements] = useState([]);
  const [timetable, setTimetable] = useState([]);
  const [forecasts, setForecasts] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [apiErrors, setApiErrors] = useState({});
  const [optimizationResult, setOptimizationResult] = useState(null);

  // Interactive UI State
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [optimizationStep, setOptimizationStep] = useState(0);
  const [selectedDetailBlock, setSelectedDetailBlock] = useState(null);
  const [toasts, setToasts] = useState([]);

  const addToast = (message, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Fetch all primary operational telemetry
  const fetchAllData = useCallback(async () => {
    setLoading(true);
    try {
      const health = await checkBackendHealth();
      setIsOnline(health.online);

      // Fetch all operational data in parallel
      const [
        blocksRes,
        maintRes,
        trainsRes,
        movementsRes,
        timetableRes,
        forecastRes,
        conflictRes,
      ] = await Promise.allSettled([
        getBlocks({ limit: 200 }),
        getMaintenance({ limit: 200 }),
        getTrains({ limit: 200 }),
        getMovements({ limit: 200 }),
        getTimetable({ service_date: targetDate, limit: 500 }),
        getGoodsForecast({ target_date: targetDate }),
        detectConflicts(targetDate, 15),
      ]);

      const errors = {};

      if (blocksRes.status === 'fulfilled' && blocksRes.value?.data) {
        setBlocks(blocksRes.value.data);
      } else if (blocksRes.status === 'rejected') {
        errors.blocks = blocksRes.reason?.message || 'Failed to load block requests';
      }

      if (maintRes.status === 'fulfilled' && maintRes.value?.data) {
        setMaintenance(maintRes.value.data);
      } else if (maintRes.status === 'rejected') {
        errors.maintenance = maintRes.reason?.message || 'Failed to load maintenance records';
      }

      if (trainsRes.status === 'fulfilled' && trainsRes.value?.data) {
        setTrains(trainsRes.value.data);
      } else if (trainsRes.status === 'rejected') {
        errors.trains = trainsRes.reason?.message || 'Failed to load trains telemetry';
      }

      if (movementsRes.status === 'fulfilled' && movementsRes.value?.data) {
        setMovements(movementsRes.value.data);
      } else if (movementsRes.status === 'rejected') {
        errors.movements = movementsRes.reason?.message || 'Failed to load train movements';
      }

      if (timetableRes.status === 'fulfilled' && timetableRes.value?.data) {
        setTimetable(timetableRes.value.data);
      } else if (timetableRes.status === 'rejected') {
        errors.timetable = timetableRes.reason?.message || 'Failed to load timetable stops';
      }

      if (forecastRes.status === 'fulfilled' && forecastRes.value?.forecasts) {
        setForecasts(forecastRes.value.forecasts);
      } else if (forecastRes.status === 'rejected') {
        errors.forecast = forecastRes.reason?.message || 'Failed to generate goods forecast';
      }

      if (conflictRes.status === 'fulfilled' && conflictRes.value?.conflicts) {
        setConflicts(conflictRes.value.conflicts);
      } else if (conflictRes.status === 'rejected') {
        errors.conflicts = conflictRes.reason?.message || 'Failed to detect operational conflicts';
      }

      setApiErrors(errors);

      // ----- Phase 5: Restore latest persisted optimization result -----
      // Only attempt if no result already in memory (e.g. on initial load / date change)
      if (!optimizationResult) {
        try {
          const storedPlan = await getLatestOptimizedPlan(targetDate);
          if (storedPlan && storedPlan.result) {
            setOptimizationResult(storedPlan.result);
            const meta = storedPlan.plan_meta;
            addToast(
              `Restored persisted plan (${meta?.plan_id || 'unknown'}) for ${targetDate}: ` +
              `${meta?.num_scheduled ?? '?'} scheduled, status: ${meta?.solver_status ?? '?'}.`,
              'info'
            );
          }
        } catch (planErr) {
          // Non-fatal — the user can run optimization manually
          console.info('No persisted optimization plan to restore for', targetDate, planErr?.message);
        }
      }

      if (Object.keys(errors).length > 0) {
        addToast(`Telemetry issue in ${Object.keys(errors).length} service(s).`, 'warning');
      }
    } catch (err) {
      console.error('Failed fetching telemetry:', err);
      setIsOnline(false);
      addToast('Backend connectivity issue. Ensure FastAPI is running on port 8000.', 'error');
    } finally {
      setLoading(false);
    }
  }, [targetDate]);

  useEffect(() => {
    // Clear in-memory optimization result when date changes so the restore
    // logic in fetchAllData will attempt to retrieve the plan for the new date.
    setOptimizationResult(null);
    fetchAllData();
  }, [fetchAllData]);


  // Periodic health check
  useEffect(() => {
    const interval = setInterval(async () => {
      const h = await checkBackendHealth();
      setIsOnline(h.online);
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  // CP-SAT Mathematical Optimization Flow
  const handleRunOptimization = async (customParams = {}) => {
    setIsOptimizing(true);
    setOptimizationStep(1);

    try {
      await new Promise((r) => setTimeout(r, 400));
      setOptimizationStep(2);

      const result = await optimizePlan({
        target_date: customParams.target_date || targetDate,
        horizon_days: customParams.horizon_days || 7,
        buffer_minutes: customParams.buffer_minutes || 15,
        include_forecast: customParams.include_forecast !== false,
      });

      setOptimizationStep(3);
      setOptimizationResult(result);

      const numSched = result.solver_statistics?.num_scheduled ?? result.scheduled_blocks?.length ?? 0;
      const numUnsched = result.solver_statistics?.num_unscheduled ?? result.unscheduled_blocks?.length ?? 0;
      const numAvoided = result.solver_statistics?.num_conflicts_avoided ?? 0;

      addToast(
        `CP-SAT Optimization Complete: ${numSched} Scheduled, ${numUnsched} Unscheduled, ${numAvoided} Headway Collisions Avoided.`,
        'success'
      );
    } catch (err) {
      console.error('Optimization failed:', err);
      addToast(`Optimization error: ${err.message || 'Solver execution failed'}`, 'error');
    } finally {
      setIsOptimizing(false);
      setOptimizationStep(0);
    }
  };

  const handleRunForecast = async () => {
    try {
      addToast('Running goods train trajectory prediction...', 'info');
      const fc = await runGoodsForecast({ target_date: targetDate, horizon_hours: 24 });
      if (fc && fc.forecasts) {
        setForecasts(fc.forecasts);
        addToast(`Forecast generated: ${fc.forecasts.length} active freight windows predicted.`, 'success');
      }
    } catch (err) {
      addToast(`Forecasting error: ${err.message}`, 'error');
    }
  };

  const getPageTitle = () => {
    switch (activePage) {
      case 'dashboard': return 'Operations Dashboard';
      case 'schedule': return 'Optimized Schedule';
      case 'optimization': return 'CP-SAT Optimization Engine';
      case 'blocks': return 'Block Disconnections';
      case 'maintenance': return 'Scheduled Maintenance';
      case 'trains': return 'Live Train Traffic';
      case 'forecast': return 'Goods Train Forecast';
      case 'conflicts': return 'Incident & Conflict Center';
      default: return 'Railway Block Planner';
    }
  };

  return (
    <div className="app-shell">
      {/* Persistent Sidebar */}
      <Sidebar
        activePage={activePage}
        setActivePage={setActivePage}
        isOnline={isOnline}
        conflictCount={conflicts.length}
        forecastCount={forecasts.length}
      />

      {/* Main Content Area */}
      <div className="main-wrapper">
        <Header
          pageTitle={getPageTitle()}
          pageTag={activePage.toUpperCase()}
          targetDate={targetDate}
          onDateChange={setTargetDate}
          isOnline={isOnline}
          onRunOptimization={() => handleRunOptimization({ target_date: targetDate, horizon_days: 7 })}
          isOptimizing={isOptimizing}
          onRefresh={fetchAllData}
        />

        <main className="main-content">
          {activePage === 'dashboard' && (
            <Dashboard
              targetDate={targetDate}
              optimizationResult={optimizationResult}
              isOptimizing={isOptimizing}
              onRunOptimization={handleRunOptimization}
              blocks={blocks}
              conflicts={conflicts}
              forecasts={forecasts}
              trains={trains}
              onSelectBlock={setSelectedDetailBlock}
              loading={loading}
              error={apiErrors.blocks || apiErrors.conflicts}
              onRetry={fetchAllData}
            />
          )}

          {activePage === 'schedule' && (
            <Schedule
              blocks={blocks}
              timetable={timetable}
              optimizationResult={optimizationResult}
              targetDate={targetDate}
              onSelectBlock={setSelectedDetailBlock}
              loading={loading}
              error={apiErrors.blocks || apiErrors.timetable}
              onRetry={fetchAllData}
            />
          )}

          {activePage === 'optimization' && (
            <Optimization
              targetDate={targetDate}
              onRunOptimization={handleRunOptimization}
              isOptimizing={isOptimizing}
              optimizationResult={optimizationResult}
              optimizationStep={optimizationStep}
              onSelectBlock={setSelectedDetailBlock}
            />
          )}

          {activePage === 'blocks' && (
            <Blocks
              blocks={blocks}
              loading={loading}
              error={apiErrors.blocks}
              onRetry={fetchAllData}
              onSelectBlock={setSelectedDetailBlock}
            />
          )}

          {activePage === 'maintenance' && (
            <Maintenance
              maintenanceRecords={maintenance}
              loading={loading}
              error={apiErrors.maintenance}
              onRetry={fetchAllData}
              onSelectBlock={setSelectedDetailBlock}
            />
          )}

          {activePage === 'trains' && (
            <Trains
              trains={trains}
              movements={movements}
              loading={loading}
              error={apiErrors.trains || apiErrors.movements}
              onRetry={fetchAllData}
            />
          )}

          {activePage === 'forecast' && (
            <Forecast
              forecasts={forecasts}
              loading={loading}
              error={apiErrors.forecast}
              onRetry={fetchAllData}
              onRunForecast={handleRunForecast}
              targetDate={targetDate}
            />
          )}

          {activePage === 'conflicts' && (
            <Conflicts
              conflicts={conflicts}
              blocks={blocks}
              loading={loading}
              error={apiErrors.conflicts}
              onRetry={fetchAllData}
              targetDate={targetDate}
            />
          )}
        </main>
      </div>

      {/* Slide-out Block Detail Modal */}
      {selectedDetailBlock && (
        <BlockDetailModal
          block={selectedDetailBlock}
          onClose={() => setSelectedDetailBlock(null)}
          onSave={fetchAllData}
        />
      )}

      {/* Floating System Toasts */}
      <Toast toasts={toasts} onDismiss={removeToast} />
    </div>
  );
}
