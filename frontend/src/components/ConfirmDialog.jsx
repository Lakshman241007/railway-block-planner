import React from 'react';

const ICONS = {
  danger: '⚠',
  warning: '❕',
  neutral: '?',
};

/**
 * Standardized confirmation dialog for destructive or consequential actions
 * (cancelling a block, rejecting a request, discarding a plan). Reuses the
 * existing .modal-overlay / .modal-dialog shell from the Modals system so it
 * stacks and behaves identically to other modals.
 *
 *   <ConfirmDialog
 *     open={showConfirm}
 *     tone="danger"
 *     title="Cancel this block request?"
 *     message="This will release the possession window and notify the requesting depot."
 *     confirmLabel="Cancel block"
 *     onConfirm={handleCancel}
 *     onClose={() => setShowConfirm(false)}
 *   />
 */
export default function ConfirmDialog({
  open,
  tone = 'neutral',
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Go back',
  onConfirm,
  onClose,
}) {
  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-dialog confirm-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="confirm-body">
          <div className={`confirm-icon ${tone}`}>{ICONS[tone] || ICONS.neutral}</div>
          {title && <div className="confirm-title">{title}</div>}
          {message && <div className="confirm-message">{message}</div>}
        </div>
        <div className="confirm-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`btn ${tone === 'danger' ? 'btn-danger' : 'btn-primary'}`}
            onClick={() => {
              onConfirm && onConfirm();
              onClose && onClose();
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
