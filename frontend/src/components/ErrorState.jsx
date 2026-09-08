import React from 'react';

export default function ErrorState({
  title = 'Unable to Load Data',
  message = 'An error occurred while connecting to the Railway Block Planner API.',
  onRetry,
}) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '40px 20px',
        textAlign: 'center',
        gap: 12,
        background: 'rgba(239, 68, 68, 0.05)',
        border: '1px solid rgba(239, 68, 68, 0.2)',
        borderRadius: 8,
      }}
    >
      <div style={{ fontSize: '2rem' }}>⚠️</div>
      <div style={{ color: '#f87171', fontWeight: 700, fontSize: '0.95rem' }}>{title}</div>
      <div style={{ color: '#94a3b8', fontSize: '0.8rem', maxWidth: 450 }}>{message}</div>
      {onRetry && (
        <button className="btn btn-secondary btn-sm" onClick={onRetry} style={{ marginTop: 6 }}>
          🔄 Retry
        </button>
      )}
    </div>
  );
}
