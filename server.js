import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import {
  db,
  loadCSVFiles,
  generateGoodsForecast,
  findFeasibleSlots,
  runHeuristicScheduler,
  detectConflicts,
  runCP_SAT_Optimizer
} from './server_db.js';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// ==========================================================================
// Health & Diagnostic Endpoints
// ==========================================================================

app.get('/health', (req, res) => {
  res.json({
    status: "OK",
    timestamp: new Date().toISOString(),
    service: "Railway Block Planner API Engine",
    version: "1.0.0",
    data_counts: {
      trains: db.trains.length,
      movements: db.movements.length,
      maintenance: db.maintenance.length,
      blocks: db.blocks.length,
      timetable: db.timetable.length,
      optimized_plans: db.optimizedPlans.length
    }
  });
});

// ==========================================================================
// Trains API
// ==========================================================================

app.get('/api/trains', (req, res) => {
  let list = db.trains;
  const { status, skip, limit } = req.query;

  if (status) {
    list = list.filter(t => (t.status || "").toLowerCase() === String(status).toLowerCase());
  }

  const offset = parseInt(skip, 10) || 0;
  const size = parseInt(limit, 10) || 100;
  
  res.json({
    data: list.slice(offset, offset + size),
    count: list.slice(offset, offset + size).length,
    total: list.length
  });
});

app.get('/api/trains/:train_id', (req, res) => {
  const train = db.trains.find(t => t.train_id.toUpperCase() === req.params.train_id.toUpperCase());
  if (!train) {
    return res.status(404).json({ error: `Train '${req.params.train_id}' not found.` });
  }
  res.json(train);
});

// ==========================================================================
// Maintenance API
// ==========================================================================

app.get('/api/maintenance', (req, res) => {
  let list = db.maintenance;
  const { priority, status, asset_id, skip, limit } = req.query;

  if (priority) {
    list = list.filter(m => (m.priority || "").toLowerCase() === String(priority).toLowerCase());
  }
  if (status) {
    list = list.filter(m => (m.status || "").toLowerCase() === String(status).toLowerCase());
  }
  if (asset_id) {
    list = list.filter(m => (m.asset_id || "").toLowerCase() === String(asset_id).toLowerCase());
  }

  const offset = parseInt(skip, 10) || 0;
  const size = parseInt(limit, 10) || 100;

  res.json({
    data: list.slice(offset, offset + size),
    count: list.slice(offset, offset + size).length,
    total: list.length
  });
});

app.get('/api/maintenance/:assetId', (req, res) => {
  const item = db.maintenance.find(m => m.asset_id.toLowerCase() === req.params.assetId.toLowerCase());
  if (!item) {
    return res.status(404).json({ error: `Maintenance item with asset ID '${req.params.assetId}' not found.` });
  }
  res.json(item);
});

app.patch('/api/maintenance/:id', (req, res) => {
  const item = db.maintenance.find(m => String(m.id) === String(req.params.id) || m.asset_id === req.params.id);
  if (!item) {
    return res.status(404).json({ error: "Maintenance record not found." });
  }
  Object.assign(item, req.body);
  res.json(item);
});

// ==========================================================================
// Blocks (Possessions) API
// ==========================================================================

app.get('/api/blocks', (req, res) => {
  let list = db.blocks;
  const { status, skip, limit, location, date } = req.query;

  if (status) {
    list = list.filter(b => (b.status || "").toLowerCase() === String(status).toLowerCase());
  }
  if (location) {
    list = list.filter(b => (b.location || "").toLowerCase().includes(String(location).toLowerCase()));
  }
  if (date) {
    list = list.filter(b => b.requested_date === date);
  }

  const offset = parseInt(skip, 10) || 0;
  const size = parseInt(limit, 10) || 100;

  res.json({
    data: list.slice(offset, offset + size),
    count: list.slice(offset, offset + size).length,
    total: list.length
  });
});

app.get('/api/blocks/:block_id', (req, res) => {
  const block = db.blocks.find(b => b.block_id.toLowerCase() === req.params.block_id.toLowerCase());
  if (!block) {
    return res.status(404).json({ error: `Block request '${req.params.block_id}' not found.` });
  }
  res.json(block);
});

app.post('/api/blocks', (req, res) => {
  const { block_id, location, block_type, requested_date, requested_start, requested_end, priority, reason } = req.body;

  if (!block_id || !location || !requested_date || !requested_start || !requested_end) {
    return res.status(422).json({ error: "Missing required fields." });
  }

  // Validate dates YYYY-MM-DD
  const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
  if (!dateRegex.test(requested_date)) {
    return res.status(422).json({ error: "Invalid date format. Expected YYYY-MM-DD" });
  }

  // Add new block record
  const newBlock = {
    id: db.blocks.length + 1,
    block_id,
    location,
    block_type: block_type || "Track",
    requested_date,
    requested_start,
    requested_end,
    priority: priority || "Medium",
    status: "Requested",
    reason: reason || "",
    source: "bdms"
  };

  db.blocks.push(newBlock);
  res.status(201).json(newBlock);
});

app.patch('/api/blocks/:block_id', (req, res) => {
  const block = db.blocks.find(b => b.block_id.toLowerCase() === req.params.block_id.toLowerCase());
  if (!block) {
    return res.status(404).json({ error: "Block request not found." });
  }
  Object.assign(block, req.body);
  res.json(block);
});

// ==========================================================================
// Train Movements API (COA)
// ==========================================================================

app.get('/api/movements', (req, res) => {
  let list = db.movements;
  const { train_id, section, skip, limit } = req.query;

  if (train_id) {
    list = list.filter(m => m.train_id.toUpperCase() === String(train_id).toUpperCase());
  }
  if (section) {
    list = list.filter(m => m.section.toLowerCase().includes(String(section).toLowerCase()));
  }

  const offset = parseInt(skip, 10) || 0;
  const size = parseInt(limit, 10) || 100;

  res.json({
    data: list.slice(offset, offset + size),
    count: list.slice(offset, offset + size).length,
    total: list.length
  });
});

app.get('/api/movements/train/:trainId', (req, res) => {
  const list = db.movements.filter(m => m.train_id.toUpperCase() === req.params.trainId.toUpperCase());
  res.json(list);
});

app.get('/api/movements/section/:section', (req, res) => {
  const list = db.movements.filter(m => m.section.toLowerCase().includes(req.params.section.toLowerCase()));
  res.json(list);
});

app.get('/api/movements/:id', (req, res) => {
  const item = db.movements.find(m => String(m.id) === String(req.params.id));
  if (!item) {
    return res.status(404).json({ error: "Movement record not found." });
  }
  res.json(item);
});

// ==========================================================================
// Passenger Timetable API
// ==========================================================================

app.get('/api/timetable', (req, res) => {
  let list = db.timetable;
  const { train_id, service_date, skip, limit } = req.query;

  if (train_id) {
    list = list.filter(t => t.train_id.toUpperCase() === String(train_id).toUpperCase());
  }
  if (service_date) {
    list = list.filter(t => t.service_date === service_date);
  }

  const offset = parseInt(skip, 10) || 0;
  const size = parseInt(limit, 10) || 100;

  res.json({
    data: list.slice(offset, offset + size),
    count: list.slice(offset, offset + size).length,
    total: list.length
  });
});

app.get('/api/timetable/train/:trainId', (req, res) => {
  const list = db.timetable.filter(t => t.train_id.toUpperCase() === req.params.trainId.toUpperCase());
  res.json(list);
});

app.get('/api/timetable/:id', (req, res) => {
  const item = db.timetable.find(t => String(t.id) === String(req.params.id));
  if (!item) {
    return res.status(404).json({ error: "Timetable slot not found." });
  }
  res.json(item);
});

// ==========================================================================
// Goods Train Forecasting API
// ==========================================================================

app.get('/api/forecast', (req, res) => {
  const { target_date, train_id, section } = req.query;
  const dateStr = target_date || new Date().toISOString().split('T')[0];
  const result = generateGoodsForecast(dateStr, db, train_id, section);
  res.json(result);
});

// ==========================================================================
// Plans (Planning View & CP-SAT Results) API
// ==========================================================================

app.get('/api/plans', (req, res) => {
  let list = db.blocks;
  const { status, skip, limit } = req.query;

  if (status) {
    list = list.filter(b => (b.status || "").toLowerCase() === String(status).toLowerCase());
  }

  const offset = parseInt(skip, 10) || 0;
  const size = parseInt(limit, 10) || 100;

  res.json({
    data: list.slice(offset, offset + size),
    count: list.slice(offset, offset + size).length,
    total: list.length,
    note: "Use POST /api/plans/optimize to run CP-SAT optimization. Use GET /api/plans/optimized to retrieve persisted plans."
  });
});

app.get('/api/plans/optimized', (req, res) => {
  const { target_date, skip, limit } = req.query;
  let list = [...db.optimizedPlans];

  if (target_date) {
    list = list.filter(p => p.target_date === target_date);
  }

  // Sort newest first
  list.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  const offset = parseInt(skip, 10) || 0;
  const size = parseInt(limit, 10) || 50;

  const summaries = list.slice(offset, offset + size).map(p => ({
    plan_id: p.plan_id,
    target_date: p.target_date,
    horizon_days: p.horizon_days,
    solver_status: p.solver_status,
    objective_value: p.objective_value,
    num_scheduled: p.num_scheduled,
    num_unscheduled: p.num_unscheduled,
    total_requests: p.total_requests,
    conflicts_before: p.conflicts_before,
    conflicts_after: p.conflicts_after,
    wall_time_seconds: p.wall_time_seconds,
    created_at: p.created_at
  }));

  res.json({
    data: summaries,
    count: summaries.length,
    total: list.length
  });
});

app.get('/api/plans/optimized/latest', (req, res) => {
  const target_d_str = req.query.target_date || new Date().toISOString().split('T')[0];
  const matchedPlans = db.optimizedPlans.filter(p => p.target_date === target_d_str);

  if (matchedPlans.length === 0) {
    return res.status(404).json({
      error: `No optimized plan found for target date '${target_d_str}'. Run POST /api/plans/optimize first.`
    });
  }

  // Order by created_at desc
  matchedPlans.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  const plan = matchedPlans[0];

  try {
    const resultData = JSON.parse(plan.result_json);
    res.json({
      plan_meta: {
        plan_id: plan.plan_id,
        target_date: plan.target_date,
        horizon_days: plan.horizon_days,
        solver_status: plan.solver_status,
        created_at: plan.created_at
      },
      result: resultData
    });
  } catch (err) {
    res.status(500).json({ error: `Stored plan '${plan.plan_id}' has corrupted JSON payload: ${err.message}` });
  }
});

app.get('/api/plans/optimized/:plan_id', (req, res) => {
  const plan = db.optimizedPlans.find(p => p.plan_id.toLowerCase() === req.params.plan_id.toLowerCase());
  if (!plan) {
    return res.status(404).json({ error: `Optimized plan '${req.params.plan_id}' not found.` });
  }

  try {
    const resultData = JSON.parse(plan.result_json);
    res.json({
      plan_meta: {
        plan_id: plan.plan_id,
        target_date: plan.target_date,
        horizon_days: plan.horizon_days,
        solver_status: plan.solver_status,
        created_at: plan.created_at
      },
      result: resultData
    });
  } catch (err) {
    res.status(500).json({ error: `Stored plan '${plan.plan_id}' has corrupted JSON payload: ${err.message}` });
  }
});

app.post('/api/plans/generate', (req, res) => {
  const request = req.body || {};
  const targetDateStr = request.target_date || new Date().toISOString().split('T')[0];
  const schedResult = runHeuristicScheduler(targetDateStr, request.priority_filter, request.location_filter);
  const conflictReport = detectConflicts(targetDateStr, schedResult);
  const fcResult = generateGoodsForecast(targetDateStr, db);

  res.json({
    plan_id: `GEN-${String(Math.floor(Math.random() * 100000)).padStart(5, '0')}`,
    generated_at: new Date().toISOString(),
    target_date: targetDateStr,
    phase: "Phase 4 - Forecast + Scheduler + Conflict Detection",
    forecast_summary: {
      total_trains: fcResult.total_trains_forecasted,
      total_windows: fcResult.total_section_windows,
      average_confidence: fcResult.average_confidence
    },
    schedule: schedResult,
    conflict_report: conflictReport,
    resolution_recommendations: conflictReport.conflicts.map(c => ({
      title: `${c.conflict_type} Resolution Strategy`,
      description: c.suggested_action
    }))
  });
});

app.post('/api/plans/reset', (req, res) => {
  loadCSVFiles();
  db.optimizedPlans = [];
  res.json({
    status: "success",
    message: "Database successfully reset to baseline un-optimized state.",
    statistics: {
      trains: db.trains.length,
      movements: db.movements.length,
      maintenance: db.maintenance.length,
      blocks: db.blocks.length,
      timetable: db.timetable.length
    },
    target_date: "2026-09-07"
  });
});

app.post('/api/plans/optimize', (req, res) => {
  const request = req.body || {};
  const result = runCP_SAT_Optimizer(request);
  res.json(result);
});

// ==========================================================================
// Scheduler Interface APIs (Conflicts & Slots)
// ==========================================================================

app.get('/api/scheduler/conflicts', (req, res) => {
  const targetDateStr = req.query.target_date || new Date().toISOString().split('T')[0];
  const useOptimized = req.query.use_optimized !== 'false' && req.query.use_optimized !== false;
  
  let proposedSchedule = null;
  if (useOptimized) {
    const matchedPlans = db.optimizedPlans.filter(p => p.target_date === targetDateStr);
    if (matchedPlans.length > 0) {
      matchedPlans.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      try {
        const parsed = JSON.parse(matchedPlans[0].result_json);
        proposedSchedule = parsed.scheduled_blocks;
      } catch (err) {
        console.error("Error parsing latest plan for conflict evaluation:", err);
      }
    }
  }

  const report = detectConflicts(targetDateStr, proposedSchedule);
  res.json(report);
});

app.post('/api/scheduler/conflicts', (req, res) => {
  const { target_date, proposed_schedule, use_optimized } = req.body || {};
  const targetDateStr = target_date || req.query.target_date || new Date().toISOString().split('T')[0];
  let scheduleToUse = proposed_schedule;

  if (!scheduleToUse && (use_optimized !== false && req.query.use_optimized !== 'false')) {
    const matchedPlans = db.optimizedPlans.filter(p => p.target_date === targetDateStr);
    if (matchedPlans.length > 0) {
      matchedPlans.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      try {
        const parsed = JSON.parse(matchedPlans[0].result_json);
        scheduleToUse = parsed.scheduled_blocks;
      } catch (err) {
        console.error("Error parsing latest plan:", err);
      }
    }
  }

  const report = detectConflicts(targetDateStr, scheduleToUse);
  res.json(report);
});

app.post('/api/scheduler/feasible-slots', (req, res) => {
  const { location, duration_minutes, preferred_start, target_date, max_slots } = req.body || {};
  if (!location || !duration_minutes) {
    return res.status(422).json({ error: "Missing required arguments: location, duration_minutes" });
  }
  const dateStr = target_date || new Date().toISOString().split('T')[0];
  const list = findFeasibleSlots(location, duration_minutes, preferred_start, dateStr, max_slots || 5);
  res.json(list);
});

app.post('/api/scheduler/schedule', (req, res) => {
  const { target_date, priority_filter, location_filter } = req.body || {};
  const dateStr = target_date || new Date().toISOString().split('T')[0];
  const schedResult = runHeuristicScheduler(dateStr, priority_filter, location_filter);
  res.json(schedResult);
});

// ==========================================================================
// Phase 9: Conflict Review & Human Verification API
// ==========================================================================

// In-memory conflict resolution tracking
if (!db.conflictReviews) {
  db.conflictReviews = new Map();
}
if (!db.publishedPlans) {
  db.publishedPlans = [];
}

app.get(['/api/conflicts/review', '/api/conflicts/review/all'], (req, res) => {
  const targetDateStr = req.query.target_date || new Date().toISOString().split('T')[0];
  const report = detectConflicts(targetDateStr);
  const reviewed = report.conflicts.map(c => {
    const reviewData = db.conflictReviews.get(c.conflict_id);
    if (reviewData) {
      return { ...c, ...reviewData };
    }
    return {
      ...c,
      review_status: c.auto_resolved ? 'AUTO_RESOLVED' : 'REQUIRES_HUMAN_REVIEW',
    };
  });

  res.json({
    data: reviewed,
    count: reviewed.length,
    unresolved_count: reviewed.filter(c => c.review_status === 'REQUIRES_HUMAN_REVIEW').length,
  });
});

app.post('/api/conflicts/process', (req, res) => {
  const { target_date } = req.body || {};
  const targetDateStr = target_date || new Date().toISOString().split('T')[0];
  const report = detectConflicts(targetDateStr);
  res.json(report);
});

app.post('/api/conflicts/:conflict_id/resolve', (req, res) => {
  const conflictId = req.params.conflict_id;
  const payload = req.body || {};
  const review = {
    review_status: 'HUMAN_RESOLVED',
    status: 'HUMAN_RESOLVED',
    resolution_action: payload.action || 'ACCEPT_RECOMMENDATION',
    notes: payload.notes || 'Resolved by human operator',
    resolved_at: new Date().toISOString(),
  };
  db.conflictReviews.set(conflictId, review);
  res.json({ success: true, conflict_id: conflictId, ...review });
});

app.post('/api/conflicts/:conflict_id/reject', (req, res) => {
  const conflictId = req.params.conflict_id;
  const payload = req.body || {};
  const review = {
    review_status: 'REJECTED',
    status: 'REJECTED',
    rejection_reason: payload.reason || 'Rejected by operator',
    notes: payload.notes || '',
    rejected_at: new Date().toISOString(),
  };
  db.conflictReviews.set(conflictId, review);
  res.json({ success: true, conflict_id: conflictId, ...review });
});

app.post('/api/conflicts/:conflict_id/defer', (req, res) => {
  const conflictId = req.params.conflict_id;
  const payload = req.body || {};
  const review = {
    review_status: 'DEFERRED',
    status: 'DEFERRED',
    defer_reason: payload.reason || 'Deferred to next cycle',
    defer_until: payload.defer_until || null,
    deferred_at: new Date().toISOString(),
  };
  db.conflictReviews.set(conflictId, review);
  res.json({ success: true, conflict_id: conflictId, ...review });
});

// ==========================================================================
// Phase 9: Plan Approval & Publication API
// ==========================================================================

app.get('/api/plans/published', (req, res) => {
  const targetDateStr = req.query.target_date;
  let list = db.publishedPlans || [];
  if (targetDateStr) {
    list = list.filter(p => p.target_date === targetDateStr);
  }
  res.json({ data: list, count: list.length, total: list.length });
});

app.post('/api/plans/:plan_id/approve', (req, res) => {
  const planId = req.params.plan_id;
  const payload = req.body || {};
  res.json({
    success: true,
    plan_id: planId,
    approval_status: 'APPROVED',
    approved: true,
    approved_at: new Date().toISOString(),
    notes: payload.notes || 'Approved by operator',
  });
});

app.post('/api/plans/:plan_id/publish', (req, res) => {
  const planId = req.params.plan_id;
  const payload = req.body || {};
  const publishedEntry = {
    plan_id: planId,
    approval_status: 'PUBLISHED',
    published: true,
    published_at: new Date().toISOString(),
    notes: payload.notes || 'Published to operational network',
  };
  db.publishedPlans.push(publishedEntry);
  res.json({ success: true, ...publishedEntry });
});

app.post('/api/plans/:plan_id/reject', (req, res) => {
  const planId = req.params.plan_id;
  const payload = req.body || {};
  res.json({
    success: true,
    plan_id: planId,
    approval_status: 'REJECTED',
    rejection_reason: payload.reason || 'Rejected by operator',
  });
});

// ==========================================================================
// Vite Integration / Frontend Static Assets
// ==========================================================================

const isProd = process.env.NODE_ENV === 'production';

if (!isProd) {
  console.log("Starting backend in DEVELOPMENT mode with Vite dev middleware...");
  const { createServer } = await import('vite');
  const vite = await createServer({
    server: { middlewareMode: true },
    appType: 'custom',
    root: path.resolve('frontend')
  });
  app.use(vite.middlewares);
  app.use('*', async (req, res, next) => {
    try {
      const url = req.originalUrl;
      let template = fs.readFileSync(path.resolve('frontend/index.html'), 'utf-8');
      template = await vite.transformIndexHtml(url, template);
      res.status(200).set({ 'Content-Type': 'text/html' }).end(template);
    } catch (e) {
      vite.ssrFixStacktrace(e);
      next(e);
    }
  });
} else {
  console.log("Starting backend in PRODUCTION mode, serving compiled assets...");
  app.use(express.static(path.resolve('frontend/dist')));
  app.get('*', (req, res) => {
    res.sendFile(path.resolve('frontend/dist/index.html'));
  });
}

app.listen(PORT, '0.0.0.0', () => {
  console.log(`================================================================`);
  console.log(`Railway Block Planner API Engine listening on http://0.0.0.0:${PORT}`);
  console.log(`================================================================`);
});
