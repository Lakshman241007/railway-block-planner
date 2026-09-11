import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { AuthProvider, useAuth, ROLES } from './auth/AuthContext';
import {
  OPERATOR_ROUTES,
  EMPLOYEE_ROUTES,
  getCurrentPath,
  navigateTo,
  resolveRoute,
} from './router';

// Component imports
import Header from './components/Header';
import OperatorSidebar from './components/operator/OperatorSidebar';
import EmployeeSidebar from './components/employee/EmployeeSidebar';
import BlockDetailModal from './components/BlockDetailModal';
import EmployeeBlockDetailModal from './components/employee/EmployeeBlockDetailModal';
import Toast from './components/Toast';

// Operator Pages
import OperatorDashboard from './pages/operator/OperatorDashboard';
import OperatorSchedule from './pages/operator/OperatorSchedule';
import OperatorBlockRequests from './pages/operator/OperatorBlockRequests';
import OperatorMaintenance from './pages/operator/OperatorMaintenance';
import OperatorTrains from './pages/operator/OperatorTrains';
import OperatorForecast from './pages/operator/OperatorForecast';
import OperatorOptimization from './pages/operator/OperatorOptimization';
import OperatorConflicts from './pages/operator/OperatorConflicts';

// Employee Pages
import EmployeeDashboard from './pages/employee/EmployeeDashboard';
import EmployeeSchedule from './pages/employee/EmployeeSchedule';
import EmployeeBlocks from './pages/employee/EmployeeBlocks';
import EmployeeMaintenance from './pages/employee/EmployeeMaintenance';
import EmployeeTrainTraffic from './pages/employee/EmployeeTrainTraffic';
import EmployeeForecast from './pages/employee/EmployeeForecast';
import EmployeePlanStatus from './pages/employee/EmployeePlanStatus';
import EmployeeConflicts from './pages/employee/EmployeeConflicts';

// API Services
import { checkBackendHealth } from './services/api';
import { getBlocks } from './services/blocks';
import { getMaintenance } from './services/maintenance';
import { getTrains } from './services/trains';
import { getMovements } from './services/movements';
import { getTimetable } from './services/timetable';
import { getGoodsForecast, runGoodsForecast } from './services/forecast';
import { detectConflicts } from './services/scheduler';
import { optimizePlan, getLatestOptimizedPlan, resetOptimizationBaseline } from './services/plans';

function AppContent() {
  const { role, isOperator, isEmployee, setRole } = useAuth();

  // Navigation / Route State
  const [currentUrl, setCurrentUrl] = useState(() => getCurrentPath());
  const [targetDate, setTargetDate] = useState('2026-09-07');
  const [isOnline, setIsOnline] = useState(true);
  const [loading, setLoading] = useState(false);

  // Core Railway Telemetry State (shared single source of truth)
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
  const [isForecasting, setIsForecasting] = useState(false);
  const [selectedDetailBlock, setSelectedDetailBlock] = useState(null);
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  }, []);

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Sync URL changes via popstate and app:navigate
  useEffect(() => {
    const handleLocationChange = () => {
      setCurrentUrl(getCurrentPath());
    };
    window.addEventListener('popstate', handleLocationChange);
    window.addEventListener('app:navigate', handleLocationChange);
    return () => {
      window.removeEventListener('popstate', handleLocationChange);
      window.removeEventListener('app:navigate', handleLocationChange);
    };
  }, []);

  // Route resolution & Role-based enforcement
  const route = useMemo(() => {
    return resolveRoute(currentUrl, role);
  }, [currentUrl, role]);

  // Route guard: enforce that Employee cannot stay on an /operator route
  useEffect(() => {
    if (isEmployee && route.role === ROLES.OPERATOR) {
      // Map operator view to employee equivalent
      let targetPath = EMPLOYEE_ROUTES.DASHBOARD;
      if (route.page === 'schedule') targetPath = EMPLOYEE_ROUTES.SCHEDULE;
      else if (route.page === 'blocks') targetPath = EMPLOYEE_ROUTES.BLOCKS;
      else if (route.page === 'maintenance') targetPath = EMPLOYEE_ROUTES.MAINTENANCE;
      else if (route.page === 'trains') targetPath = EMPLOYEE_ROUTES.TRAINS;
      else if (route.page === 'forecast') targetPath = EMPLOYEE_ROUTES.FORECAST;
      else if (route.page === 'optimization') targetPath = EMPLOYEE_ROUTES.PLAN_STATUS;
      else if (route.page === 'conflicts') targetPath = EMPLOYEE_ROUTES.CONFLICTS;

      navigateTo(targetPath);
      addToast('Redirected to Employee Monitoring View (Read-Only)', 'info');
    }
  }, [isEmployee, route, addToast]);

  // Route guard: if Operator is on /employee route, normalize to operator equivalent
  useEffect(() => {
    if (isOperator && route.role === ROLES.EMPLOYEE) {
      let targetPath = OPERATOR_ROUTES.DASHBOARD;
      if (route.page === 'schedule') targetPath = OPERATOR_ROUTES.SCHEDULE;
      else if (route.page === 'blocks') targetPath = OPERATOR_ROUTES.BLOCKS;
      else if (route.page === 'maintenance') targetPath = OPERATOR_ROUTES.MAINTENANCE;
      else if (route.page === 'trains') targetPath = OPERATOR_ROUTES.TRAINS;
      else if (route.page === 'forecast') targetPath = OPERATOR_ROUTES.FORECAST;
      else if (route.page === 'plan-status') targetPath = OPERATOR_ROUTES.OPTIMIZATION;
      else if (route.page === 'conflicts') targetPath = OPERATOR_ROUTES.CONFLICTS;

      navigateTo(targetPath);
    }
  }, [isOperator, route]);

  // Helper to switch pages
  const handlePageNavigate = (pageId, customPath) => {
    if (customPath) {
      navigateTo(customPath);
      return;
    }
    const basePath = isOperator ? '/operator' : '/employee';
    let targetPage = pageId;
    if (isEmployee && pageId === 'optimization') targetPage = 'plan-status';
    navigateTo(`${basePath}/${targetPage}`);
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

      // Restore latest persisted optimization result
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
          console.info('No persisted optimization plan to restore for', targetDate, planErr?.message);
        }
      }

      if (Object.keys(errors).length > 0) {
        addToast(`Telemetry warning in ${Object.keys(errors).length} service(s).`, 'warning');
      }
    } catch (err) {
      console.error('Failed fetching telemetry:', err);
      setIsOnline(false);
      addToast('Backend connectivity issue. Ensure FastAPI is running on port 8000.', 'error');
    } finally {
      setLoading(false);
    }
  }, [targetDate, optimizationResult, addToast]);

  useEffect(() => {
    setOptimizationResult(null);
    fetchAllData();
  }, [targetDate]); // Refetch on date change

  // Periodic health check
  useEffect(() => {
    const interval = setInterval(async () => {
      const h = await checkBackendHealth();
      setIsOnline(h.online);
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  // CP-SAT Mathematical Optimization Flow (Operator Only)
  const handleRunOptimization = async (customParams = {}) => {
    if (!isOperator) {
      addToast('Permission denied: Optimization requires Operator role.', 'error');
      return;
    }

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

      // Refresh DB block records to reflect status changes
      await fetchAllData();

      // If CP-SAT resolved all conflicts, reflect 0 conflicts in UI
      if (result.solver_statistics?.conflicts_after === 0) {
        setConflicts([]);
      }

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

  // Reset Operational Baseline (Operator Only)
  const handleResetBaseline = async () => {
    if (!isOperator) {
      addToast('Permission denied: Resetting baseline requires Operator role.', 'error');
      return;
    }

    setLoading(true);
    try {
      addToast('Resetting database to unoptimized baseline state...', 'info');
      await resetOptimizationBaseline();
      setOptimizationResult(null);
      setTargetDate('2026-09-07');
      await fetchAllData();
      addToast('Baseline restored: Database reloaded with un-scheduled requests and 15 operational conflicts.', 'success');
    } catch (err) {
      console.error('Failed to reset baseline:', err);
      addToast(`Reset error: ${err.message || 'Failed to reset database'}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  // Goods Train Forecast Trigger (Operator Only)
  const handleRunForecast = async () => {
    if (!isOperator) {
      addToast('Permission denied: Running forecast requires Operator role.', 'error');
      return;
    }

    setIsForecasting(true);
    try {
      addToast('Running goods train trajectory prediction...', 'info');
      const fc = await runGoodsForecast({ target_date: targetDate, horizon_hours: 24 });
      if (fc && fc.forecasts) {
        setForecasts(fc.forecasts);
        addToast(`Forecast generated: ${fc.forecasts.length} active freight windows predicted.`, 'success');
      }
    } catch (err) {
      addToast(`Forecasting error: ${err.message}`, 'error');
    } finally {
      setIsForecasting(false);
    }
  };

  const getPageTitle = () => {
    const page = route.page;
    if (isOperator) {
      switch (page) {
        case 'dashboard': return 'Operator Control Center';
        case 'schedule': return 'Operational Possession Schedule';
        case 'blocks': return 'Block Disconnections & Requests';
        case 'maintenance': return 'SMMS Maintenance Work Orders';
        case 'trains': return 'Live Train Traffic & Corridors';
        case 'forecast': return 'Freight Forecast Management';
        case 'optimization': return 'OR-Tools CP-SAT Optimization Deck';
        case 'conflicts': return 'Spatial-Temporal Conflict Dispatch';
        default: return 'Operator Control Center';
      }
    } else {
      switch (page) {
        case 'dashboard': return 'Employee Operations Overview';
        case 'schedule': return 'Master Operational Schedule';
        case 'blocks': return 'BDMS Block Disconnection Status';
        case 'maintenance': return 'Scheduled Maintenance Work Orders';
        case 'trains': return 'Corridor Train Traffic';
        case 'forecast': return 'Goods Train Freight Forecast';
        case 'plan-status': return 'Master Plan & Optimization Status';
        case 'conflicts': return 'Spatial-Temporal Conflict Audit';
        default: return 'Employee Operations Overview';
      }
    }
  };

  const activePageKey = route.page;

  return (
    <div className="app-shell">
      {/* Role-Specific Persistent Sidebar */}
      {isOperator ? (
        <OperatorSidebar
          activePage={activePageKey}
          onNavigate={handlePageNavigate}
          isOnline={isOnline}
          conflictCount={conflicts.length}
          forecastCount={forecasts.length}
          pendingBlockCount={blocks.filter((b) => (b.status || '').toLowerCase() === 'requested').length}
        />
      ) : (
        <EmployeeSidebar
          activePage={activePageKey}
          onNavigate={handlePageNavigate}
          isOnline={isOnline}
          conflictCount={conflicts.length}
          forecastCount={forecasts.length}
        />
      )}

      {/* Main Content Area */}
      <div className="main-wrapper">
        <Header
          pageTitle={getPageTitle()}
          pageTag={isOperator ? 'OPERATOR DECK' : 'EMPLOYEE VIEW'}
          targetDate={targetDate}
          onDateChange={setTargetDate}
          isOnline={isOnline}
          onRunOptimization={isOperator ? () => handleRunOptimization({ target_date: targetDate, horizon_days: 7 }) : null}
          onResetBaseline={isOperator ? handleResetBaseline : null}
          isOptimizing={isOptimizing}
          onRefresh={fetchAllData}
        />

        <main className="main-content">
          {/* ============================================================
              OPERATOR ROLE VIEWS
              ============================================================ */}
          {isOperator && (
            <>
              {activePageKey === 'dashboard' && (
                <OperatorDashboard
                  targetDate={targetDate}
                  optimizationResult={optimizationResult}
                  isOptimizing={isOptimizing}
                  onRunOptimization={handleRunOptimization}
                  onResetBaseline={handleResetBaseline}
                  onRunForecast={handleRunForecast}
                  isForecasting={isForecasting}
                  blocks={blocks}
                  maintenance={maintenance}
                  conflicts={conflicts}
                  forecasts={forecasts}
                  trains={trains}
                  onSelectBlock={setSelectedDetailBlock}
                  onOpenCreateBlock={() => handlePageNavigate('blocks')}
                  onNavigate={handlePageNavigate}
                  loading={loading}
                  error={apiErrors.blocks || apiErrors.conflicts}
                  onRetry={fetchAllData}
                />
              )}

              {activePageKey === 'schedule' && (
                <OperatorSchedule
                  blocks={blocks}
                  maintenance={maintenance}
                  timetable={timetable}
                  optimizationResult={optimizationResult}
                  targetDate={targetDate}
                  onSelectBlock={setSelectedDetailBlock}
                  loading={loading}
                  error={apiErrors.blocks || apiErrors.timetable}
                  onRetry={fetchAllData}
                />
              )}

              {activePageKey === 'blocks' && (
                <OperatorBlockRequests
                  blocks={blocks}
                  loading={loading}
                  error={apiErrors.blocks}
                  onRetry={fetchAllData}
                  onSelectBlock={setSelectedDetailBlock}
                />
              )}

              {activePageKey === 'maintenance' && (
                <OperatorMaintenance
                  maintenanceRecords={maintenance}
                  loading={loading}
                  error={apiErrors.maintenance}
                  onRetry={fetchAllData}
                  onSelectBlock={setSelectedDetailBlock}
                />
              )}

              {activePageKey === 'trains' && (
                <OperatorTrains
                  trains={trains}
                  movements={movements}
                  loading={loading}
                  error={apiErrors.trains || apiErrors.movements}
                  onRetry={fetchAllData}
                />
              )}

              {activePageKey === 'forecast' && (
                <OperatorForecast
                  forecasts={forecasts}
                  loading={loading}
                  error={apiErrors.forecast}
                  onRetry={fetchAllData}
                  onRunForecast={handleRunForecast}
                  targetDate={targetDate}
                />
              )}

              {activePageKey === 'optimization' && (
                <OperatorOptimization
                  targetDate={targetDate}
                  onRunOptimization={handleRunOptimization}
                  onResetBaseline={handleResetBaseline}
                  isOptimizing={isOptimizing}
                  optimizationResult={optimizationResult}
                  optimizationStep={optimizationStep}
                  onSelectBlock={setSelectedDetailBlock}
                />
              )}

              {activePageKey === 'conflicts' && (
                <OperatorConflicts
                  conflicts={conflicts}
                  blocks={blocks}
                  loading={loading}
                  error={apiErrors.conflicts}
                  onRetry={fetchAllData}
                  targetDate={targetDate}
                />
              )}
            </>
          )}

          {/* ============================================================
              EMPLOYEE ROLE VIEWS (STRICTLY READ-ONLY)
              ============================================================ */}
          {isEmployee && (
            <>
              {activePageKey === 'dashboard' && (
                <EmployeeDashboard
                  targetDate={targetDate}
                  optimizationResult={optimizationResult}
                  blocks={blocks}
                  maintenance={maintenance}
                  conflicts={conflicts}
                  forecasts={forecasts}
                  trains={trains}
                  onSelectBlock={setSelectedDetailBlock}
                  onNavigate={handlePageNavigate}
                  loading={loading}
                  error={apiErrors.blocks || apiErrors.conflicts}
                  onRetry={fetchAllData}
                />
              )}

              {activePageKey === 'schedule' && (
                <EmployeeSchedule
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

              {activePageKey === 'blocks' && (
                <EmployeeBlocks
                  blocks={blocks}
                  loading={loading}
                  error={apiErrors.blocks}
                  onRetry={fetchAllData}
                  onSelectBlock={setSelectedDetailBlock}
                />
              )}

              {activePageKey === 'maintenance' && (
                <EmployeeMaintenance
                  maintenanceRecords={maintenance}
                  loading={loading}
                  error={apiErrors.maintenance}
                  onRetry={fetchAllData}
                  onSelectBlock={setSelectedDetailBlock}
                />
              )}

              {activePageKey === 'trains' && (
                <EmployeeTrainTraffic
                  trains={trains}
                  movements={movements}
                  loading={loading}
                  error={apiErrors.trains || apiErrors.movements}
                  onRetry={fetchAllData}
                />
              )}

              {activePageKey === 'forecast' && (
                <EmployeeForecast
                  forecasts={forecasts}
                  loading={loading}
                  error={apiErrors.forecast}
                  onRetry={fetchAllData}
                  targetDate={targetDate}
                />
              )}

              {activePageKey === 'plan-status' && (
                <EmployeePlanStatus
                  optimizationResult={optimizationResult}
                  targetDate={targetDate}
                  onSelectBlock={setSelectedDetailBlock}
                />
              )}

              {activePageKey === 'conflicts' && (
                <EmployeeConflicts
                  conflicts={conflicts}
                  loading={loading}
                  error={apiErrors.conflicts}
                  onRetry={fetchAllData}
                  targetDate={targetDate}
                />
              )}
            </>
          )}
        </main>
      </div>

      {/* Role-Specific Detail Modals */}
      {selectedDetailBlock && (
        isOperator ? (
          <BlockDetailModal
            block={selectedDetailBlock}
            onClose={() => setSelectedDetailBlock(null)}
            onSave={fetchAllData}
          />
        ) : (
          <EmployeeBlockDetailModal
            block={selectedDetailBlock}
            onClose={() => setSelectedDetailBlock(null)}
          />
        )
      )}

      {/* Floating System Toasts */}
      <Toast toasts={toasts} onDismiss={removeToast} />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
