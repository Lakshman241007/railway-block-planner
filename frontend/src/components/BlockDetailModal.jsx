/**
 * @module BlockDetailModal
 * @description Operational detail inspector modal for block-disconnection and
 *              maintenance records. Supports inline editing of schedule fields
 *              (time windows, duration, priority, status, reason) with PATCH
 *              writes via the blocks / maintenance service layer.
 * @author       Railway Block Planner Team
 * @lastModified 2026-09-07
 * @dependencies components/PriorityBadge, components/StatusBadge,
 *               services/blocks → updateBlock,
 *               services/maintenance → updateMaintenance
 */

import React, { useState, useEffect } from 'react';
import PriorityBadge from './PriorityBadge';
import StatusBadge from './StatusBadge';
import { updateBlock } from '../services/blocks';
import { updateMaintenance } from '../services/maintenance';

// ---------------------------------------------------------------------------
// Field Sub-components (RULE-01.1: each function <= 60 lines)
// ---------------------------------------------------------------------------

function TimeFields({ isEditing, isBlock, block, editDraft, onDraftChange }) {
  if (!isEditing) {
    return (
      <div className="detail-item">
        <span className="detail-label">Operational Window</span>
        <span className="detail-val mono" style={{ color: '#34d399' }}>
          {block.start_time || block.requested_start || '--'} ➔{' '}
          {block.end_time || block.requested_end || '--'}
        </span>
      </div>
    );
  }

  if (isBlock) {
    return (
      <>
        <div className="detail-item">
          <span className="detail-label">Start Time</span>
          <input
            id="edit-requested-start"
            type="time"
            className="edit-field"
            value={editDraft.requested_start}
            onChange={(e) => onDraftChange('requested_start', e.target.value)}
          />
        </div>
        <div className="detail-item">
          <span className="detail-label">End Time</span>
          <input
            id="edit-requested-end"
            type="time"
            className="edit-field"
            value={editDraft.requested_end}
            onChange={(e) => onDraftChange('requested_end', e.target.value)}
          />
        </div>
      </>
    );
  }

  return (
    <div className="detail-item">
      <span className="detail-label">Preferred Start</span>
      <input
        id="edit-preferred-start"
        type="time"
        className="edit-field"
        value={editDraft.preferred_start}
        onChange={(e) => onDraftChange('preferred_start', e.target.value)}
      />
    </div>
  );
}

function DurationField({ isEditing, isMaintenance, block, editDraft, onDraftChange }) {
  if (!isEditing || !isMaintenance) {
    return (
      <div className="detail-item">
        <span className="detail-label">Duration</span>
        <span className="detail-val mono">
          {block.duration_minutes || block.required_duration || '--'} Minutes
        </span>
      </div>
    );
  }

  return (
    <div className="detail-item">
      <span className="detail-label">Duration (minutes)</span>
      <input
        id="edit-duration-minutes"
        type="number"
        min="1"
        className="edit-field"
        value={editDraft.duration_minutes}
        onChange={(e) => onDraftChange('duration_minutes', e.target.value)}
      />
    </div>
  );
}

function PriorityField({ isEditing, block, editDraft, onDraftChange }) {
  if (!isEditing) {
    return (
      <div className="detail-item">
        <span className="detail-label">Priority Tier</span>
        <div><PriorityBadge priority={block.priority} /></div>
      </div>
    );
  }

  return (
    <div className="detail-item">
      <span className="detail-label">Priority Tier</span>
      <select
        id="edit-priority"
        className="edit-field"
        value={editDraft.priority}
        onChange={(e) => onDraftChange('priority', e.target.value)}
      >
        <option value="Critical">Critical</option>
        <option value="High">High</option>
        <option value="Medium">Medium</option>
        <option value="Low">Low</option>
      </select>
    </div>
  );
}

function StatusField({ isEditing, isBlock, block, editDraft, onDraftChange }) {
  if (!isEditing) {
    return (
      <div className="detail-item">
        <span className="detail-label">Status</span>
        <div><StatusBadge status={block.status} /></div>
      </div>
    );
  }

  const blockStatuses = ['Requested', 'Approved', 'Rejected', 'Completed', 'Cancelled'];
  const maintenanceStatuses = ['Pending', 'Approved', 'Completed', 'Cancelled'];
  const options = isBlock ? blockStatuses : maintenanceStatuses;

  return (
    <div className="detail-item">
      <span className="detail-label">Status</span>
      <select
        id="edit-status"
        className="edit-field"
        value={editDraft.status}
        onChange={(e) => onDraftChange('status', e.target.value)}
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>
    </div>
  );
}

function ReasonField({ isEditing, isBlock, block, editDraft, onDraftChange }) {
  const displayText =
    block.reason ||
    block.description ||
    block.maintenance_type ||
    'Scheduled preventive corridor possession.';

  if (!isEditing || !isBlock) {
    return (
      <div className="card-detail-box" style={{ background: '#0a0e17' }}>
        <span className="detail-label">Operational Justification / Description</span>
        <span style={{ color: '#e2e8f0', fontSize: '0.8rem', lineHeight: 1.4 }}>
          {displayText}
        </span>
      </div>
    );
  }

  return (
    <div className="card-detail-box" style={{ background: '#0a0e17' }}>
      <span className="detail-label">Operational Justification / Description</span>
      <textarea
        id="edit-reason"
        className="edit-field"
        rows={3}
        value={editDraft.reason}
        onChange={(e) => onDraftChange('reason', e.target.value)}
        style={{ resize: 'vertical', minHeight: '72px' }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Structural Modal Sub-components (Header, Body, Footer)
// ---------------------------------------------------------------------------

function ModalHeader({ displayId, isOvernight, isEditing, isSaving, onStartEdit, onClose }) {
  return (
    <div className="modal-header">
      <div>
        <div style={{ fontSize: '0.7rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5 }}>
          Operational Detail Inspector
        </div>
        <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#00f0ff', fontFamily: 'var(--font-mono)' }}>
          {displayId} {isOvernight ? '🌙 (Overnight Block)' : ''}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {!isEditing && !isSaving && (
          <button
            id="modal-edit-btn"
            className="btn btn-secondary btn-sm"
            onClick={onStartEdit}
            title="Switch to edit mode"
          >
            ✏ Edit
          </button>
        )}
        <button
          className="btn btn-secondary btn-icon-only btn-sm"
          onClick={onClose}
          style={{ borderRadius: '50%' }}
          title="Close modal"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

function ModalBody({ block, sharedProps }) {
  return (
    <div className="modal-body">
      <div className="detail-grid">
        <div className="detail-item">
          <span className="detail-label">Location / Section</span>
          <span className="detail-val" style={{ fontWeight: 700 }}>
            {block.location || 'Chennai-Arakkonam'}
          </span>
        </div>

        <div className="detail-item">
          <span className="detail-label">Service Date</span>
          <span className="detail-val mono">
            {block.service_date || block.requested_date || '--'}
          </span>
        </div>

        <TimeFields {...sharedProps} />
        <DurationField {...sharedProps} />
        <PriorityField {...sharedProps} />
        <StatusField {...sharedProps} />

        <div className="detail-item">
          <span className="detail-label">Equipment / Machinery</span>
          <span className="detail-val">{block.equipment || 'Standard Track Gang'}</span>
        </div>

        <div className="detail-item">
          <span className="detail-label">Resource Gangs</span>
          <span className="detail-val mono">
            {block.required_resources || 2} Crews
          </span>
        </div>
      </div>

      <ReasonField {...sharedProps} />

      {block.reason && block.reason.toLowerCase().includes('preempt') && (
        <div
          className="card-resolution-box"
          style={{ background: 'rgba(239, 68, 68, 0.1)', borderColor: '#ef4444' }}
        >
          <strong style={{ color: '#f87171' }}>CP-SAT Solver Diagnostic:</strong>
          <div style={{ color: '#fca5a5', marginTop: 4 }}>
            This request was not scheduled because higher priority possessions saturated
            track availability or machine limits on this corridor section.
          </div>
        </div>
      )}
    </div>
  );
}

function ModalFooter({ isEditing, isSaving, saveError, onCancel, onSave, onClose }) {
  return (
    <div className="modal-footer" style={{ flexDirection: 'column', alignItems: 'stretch', gap: '10px' }}>
      {saveError && (
        <div
          id="modal-save-error"
          style={{
            background: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: '4px',
            padding: '8px 12px',
            color: '#fca5a5',
            fontSize: '0.78rem',
          }}
        >
          ⚠ {saveError}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
        {isEditing ? (
          <>
            <button
              id="modal-cancel-btn"
              className="btn btn-secondary btn-sm"
              onClick={onCancel}
              disabled={isSaving}
            >
              ✕ Cancel
            </button>
            <button
              id="modal-save-btn"
              className="btn btn-primary btn-sm"
              onClick={onSave}
              disabled={isSaving}
            >
              {isSaving ? '⏳ Saving…' : '💾 Save'}
            </button>
          </>
        ) : (
          <button
            id="modal-close-btn"
            className="btn btn-secondary btn-sm"
            onClick={onClose}
          >
            Close Inspector
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Business Logic Helpers (RULE-01.1: <= 60 lines each)
// ---------------------------------------------------------------------------

async function saveRecord(block, editDraft, isBlock, isMaintenance) {
  if (isBlock) {
    const blockId = block.block_request_id || block.block_id;
    await updateBlock(blockId, {
      requested_start: editDraft.requested_start || undefined,
      requested_end: editDraft.requested_end || undefined,
      priority: editDraft.priority || undefined,
      status: editDraft.status || undefined,
      reason: editDraft.reason || undefined,
    });
  } else if (isMaintenance) {
    const maintId = block.id != null ? block.id : (block.asset_id || block.request_id);
    const parsedDuration = editDraft.duration_minutes
      ? parseInt(editDraft.duration_minutes, 10)
      : undefined;
    await updateMaintenance(maintId, {
      preferred_start: editDraft.preferred_start || undefined,
      duration_minutes: Number.isFinite(parsedDuration) ? parsedDuration : undefined,
      priority: editDraft.priority || undefined,
      status: editDraft.status || undefined,
    });
  }
}

function createInitialDraft(block) {
  return {
    requested_start: block.requested_start || block.start_time || '',
    requested_end: block.requested_end || block.end_time || '',
    priority: block.priority || 'Medium',
    status: block.status || 'Requested',
    reason: block.reason || '',
    preferred_start: block.preferred_start || '',
    duration_minutes: block.duration_minutes != null ? String(block.duration_minutes) : '',
  };
}

function useBlockDetailDraft(block, onSave, onClose) {
  const isBlock = Boolean((block.block_id && !block.asset_id) || block.block_request_id);
  const isMaintenance = Boolean(block.asset_id && !block.block_request_id);
  const displayId = block.block_id || block.block_request_id || block.request_id || block.asset_id || 'REQ-001';
  const isOvernight =
    (block.start_time && block.end_time && block.end_time < block.start_time) ||
    (block.requested_start && block.requested_end && block.requested_end < block.requested_start);

  const [isEditing, setIsEditing] = useState(false);
  const [editDraft, setEditDraft] = useState({});
  const [saveError, setSaveError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  const resetDraft = () => {
    setEditDraft(createInitialDraft(block));
    setSaveError(null);
    setIsEditing(false);
  };

  useEffect(resetDraft, [block]);

  const handleDraftChange = (field, value) => {
    setEditDraft((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveError(null);
    try {
      await saveRecord(block, editDraft, isBlock, isMaintenance);
      if (onSave) onSave();
      onClose();
    } catch (err) {
      setSaveError(err.message || 'Save failed. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  return {
    isBlock,
    isMaintenance,
    displayId,
    isOvernight,
    isEditing,
    setIsEditing,
    editDraft,
    saveError,
    isSaving,
    handleDraftChange,
    handleCancel: resetDraft,
    handleSave,
  };
}

// ---------------------------------------------------------------------------
// Main Component (RULE-01.1: <= 60 lines)
// ---------------------------------------------------------------------------

export default function BlockDetailModal({ block, onClose, onSave }) {
  if (!block) return null;

  const {
    isBlock,
    isMaintenance,
    displayId,
    isOvernight,
    isEditing,
    setIsEditing,
    editDraft,
    saveError,
    isSaving,
    handleDraftChange,
    handleCancel,
    handleSave,
  } = useBlockDetailDraft(block, onSave, onClose);

  const sharedProps = { isEditing, isBlock, isMaintenance, block, editDraft, onDraftChange: handleDraftChange };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        <ModalHeader
          displayId={displayId}
          isOvernight={isOvernight}
          isEditing={isEditing}
          isSaving={isSaving}
          onStartEdit={() => setIsEditing(true)}
          onClose={onClose}
        />
        <ModalBody block={block} sharedProps={sharedProps} />
        <ModalFooter
          isEditing={isEditing}
          isSaving={isSaving}
          saveError={saveError}
          onCancel={handleCancel}
          onSave={handleSave}
          onClose={onClose}
        />
      </div>
    </div>
  );
}
