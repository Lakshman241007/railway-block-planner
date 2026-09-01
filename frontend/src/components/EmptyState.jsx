import React from 'react';

export default function EmptyState({
  title = 'No Records Found',
  message = 'There are no active railway operations or maintenance items for this query.',
  actionLabel,
  onAction,
  icon = '📋',
}) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '50px 20px',
        textAlign: 'center',
        gap: 12,
        background: 'rgba(255, 255, 255, 0.01)',
        border: '1px dashed #1e293b',
        borderRadius: 8,
      }}
    >
      <div style={{ fontSize: '2.2rem' }}>{icon}</div>
      <div style={{ color: '#fff', fontWeight: 700, fontSize: '0.95rem' }}>{title}</div>
      <div style={{ color: '#94a3b8', fontSize: '0.8rem', maxWidth: 400 }}>{message}</div>
      {actionLabel && (
        <button className="btn btn-secondary btn-sm" onClick={onAction} style={{ marginTop: 8 }}>
          {actionLabel}
        </button>
      )}
    </div>
  );
}
