import React, { useState } from 'react';
import PageContainer from '../components/PageContainer';
import BlockTable from '../components/BlockTable';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import { submitBlock } from '../services/blocks';

const BLOCK_TYPES = ['Maintenance', 'Emergency', 'Non-Interlocked', 'Traffic'];
const PRIORITIES = ['Low', 'Medium', 'High', 'Critical'];

const EMPTY_FORM = {
  block_id: '',
  location: '',
  block_type: 'Maintenance',
  requested_date: '',
  requested_start: '',
  requested_end: '',
  reason: '',
  priority: 'Medium',
};

export default function Blocks({ blocks = [], loading = false, error = null, onRetry, onSelectBlock }) {
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [submitSuccess, setSubmitSuccess] = useState(null);

  const handleFormChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const validateForm = () => {
    if (!form.block_id.trim()) return 'Block ID is required.';
    if (!form.location.trim()) return 'Location is required.';
    if (!form.requested_date) return 'Requested date is required.';
    if (!/^\d{4}-\d{2}-\d{2}$/.test(form.requested_date)) return 'Date must be YYYY-MM-DD.';
    if (!form.requested_start || !/^\d{2}:\d{2}$/.test(form.requested_start)) return 'Start time must be HH:MM.';
    if (!form.requested_end || !/^\d{2}:\d{2}$/.test(form.requested_end)) return 'End time must be HH:MM.';
    if (!form.reason.trim()) return 'Reason is required.';
    const s = parseInt(form.requested_start.replace(':', ''), 10);
    const e = parseInt(form.requested_end.replace(':', ''), 10);
    const sMin = Math.floor(s / 100) * 60 + (s % 100);
    const eMin = Math.floor(e / 100) * 60 + (e % 100);
    const dur = eMin < sMin ? (1440 - sMin) + eMin : eMin - sMin;
    if (dur <= 0) return 'End time and start time produce a zero-duration block. For overnight, end should be past midnight (e.g. 02:00).';
    if (dur > 1440) return 'Duration exceeds 24 hours — impossible single-possession.';
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const validationError = validateForm();
    if (validationError) {
      setSubmitError(validationError);
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(null);

    try {
      const result = await submitBlock(form);
      setSubmitSuccess(result);
      setForm(EMPTY_FORM);
      setShowForm(false);
      if (onRetry) onRetry();
    } catch (err) {
      const detail = err?.response?.detail || err?.message || 'Submission failed.';
      setSubmitError(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <PageContainer>
      {/* Success notification */}
      {submitSuccess && (
        <div style={{
          padding: '12px 18px',
          borderRadius: 6,
          background: 'rgba(16, 185, 129, 0.10)',
          border: '1px solid rgba(16, 185, 129, 0.35)',
          color: '#34d399',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          fontSize: '0.8rem',
        }}>
          <span>
            ✅ Block request <strong>{submitSuccess.block_id}</strong> validated and submitted.
            Status: <strong>{submitSuccess.status}</strong>. Duration: {submitSuccess.duration_minutes} min.
          </span>
          <button
            className="btn btn-sm btn-secondary"
            onClick={() => setSubmitSuccess(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Submit Block Request Form Panel */}
      {showForm && (
        <div className="panel" style={{ borderLeft: '3px solid #38bdf8' }}>
          <div className="panel-header">
            <div>
              <div className="panel-title">
                <span>📋 Submit BDMS Block Request</span>
                <span className="badge badge-cyan">Phase 5</span>
              </div>
              <div className="panel-subtitle">
                All fields validated against operational rules before persistence. Overnight blocks supported (e.g. 22:00 → 02:00).
              </div>
            </div>
            <button
              className="btn btn-sm btn-secondary"
              onClick={() => { setShowForm(false); setSubmitError(null); }}
            >
              Cancel
            </button>
          </div>

          <div className="panel-body">
            {submitError && (
              <div style={{
                padding: '8px 14px',
                marginBottom: 14,
                borderRadius: 4,
                background: 'rgba(239, 68, 68, 0.10)',
                border: '1px solid rgba(239, 68, 68, 0.35)',
                color: '#fca5a5',
                fontSize: '0.78rem',
              }}>
                ❌ {submitError}
              </div>
            )}

            <form onSubmit={handleSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14 }}>
                <div className="detail-item">
                  <label className="detail-label">Block ID *</label>
                  <input
                    className="search-input"
                    style={{ minWidth: '100%' }}
                    name="block_id"
                    value={form.block_id}
                    onChange={handleFormChange}
                    placeholder="e.g. BLK-099"
                    required
                    disabled={submitting}
                  />
                </div>

                <div className="detail-item">
                  <label className="detail-label">Location / Section *</label>
                  <input
                    className="search-input"
                    style={{ minWidth: '100%' }}
                    name="location"
                    value={form.location}
                    onChange={handleFormChange}
                    placeholder="e.g. Chennai-Arakkonam KM 40-42"
                    required
                    disabled={submitting}
                  />
                </div>

                <div className="detail-item">
                  <label className="detail-label">Block Type *</label>
                  <select
                    className="select-control"
                    name="block_type"
                    value={form.block_type}
                    onChange={handleFormChange}
                    disabled={submitting}
                  >
                    {BLOCK_TYPES.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>

                <div className="detail-item">
                  <label className="detail-label">Priority *</label>
                  <select
                    className="select-control"
                    name="priority"
                    value={form.priority}
                    onChange={handleFormChange}
                    disabled={submitting}
                  >
                    {PRIORITIES.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>

                <div className="detail-item">
                  <label className="detail-label">Requested Date *</label>
                  <input
                    className="select-control"
                    type="date"
                    name="requested_date"
                    value={form.requested_date}
                    onChange={handleFormChange}
                    required
                    disabled={submitting}
                  />
                </div>

                <div className="detail-item" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <div>
                    <label className="detail-label">Start Time *</label>
                    <input
                      className="select-control"
                      style={{ width: '100%' }}
                      type="time"
                      name="requested_start"
                      value={form.requested_start}
                      onChange={handleFormChange}
                      required
                      disabled={submitting}
                    />
                  </div>
                  <div>
                    <label className="detail-label">End Time * (overnight OK)</label>
                    <input
                      className="select-control"
                      style={{ width: '100%' }}
                      type="time"
                      name="requested_end"
                      value={form.requested_end}
                      onChange={handleFormChange}
                      required
                      disabled={submitting}
                    />
                  </div>
                </div>

                <div className="detail-item" style={{ gridColumn: '1 / -1' }}>
                  <label className="detail-label">Operational Reason *</label>
                  <input
                    className="search-input"
                    style={{ minWidth: '100%' }}
                    name="reason"
                    value={form.reason}
                    onChange={handleFormChange}
                    placeholder="e.g. Track geometry correction — scheduled preventive maintenance"
                    required
                    disabled={submitting}
                  />
                </div>
              </div>

              <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={submitting}
                >
                  {submitting ? '⏳ Validating & Submitting...' : '✅ Submit Block Request'}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => { setShowForm(false); setSubmitError(null); setForm(EMPTY_FORM); }}
                  disabled={submitting}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {error ? (
        <ErrorState
          title="Failed to Load Block Requests"
          message={error}
          onRetry={onRetry}
        />
      ) : loading ? (
        <LoadingState message="Fetching BDMS block requests..." />
      ) : (
        <BlockTable
          blocks={blocks}
          title="BDMS Block & Disconnection Requests"
          subtitle="Unified Block Disconnection Management System database records"
          onSelectBlock={onSelectBlock}
          showFilters={true}
          headerAction={
            !showForm && (
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setShowForm(true)}
                id="submit-block-request-btn"
              >
                + Submit Block Request
              </button>
            )
          }
        />
      )}
    </PageContainer>
  );
}
