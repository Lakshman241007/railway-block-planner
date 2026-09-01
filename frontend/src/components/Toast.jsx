import React from 'react';

export default function Toast({ toasts = [], onDismiss }) {
  if (!toasts || toasts.length === 0) return null;

  return (
    <div className="toast-container">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast ${toast.type || 'info'}`}>
          <span>{toast.type === 'error' ? '❌' : toast.type === 'success' ? '✅' : 'ℹ️'}</span>
          <div style={{ flex: 1 }}>{toast.message}</div>
          <button
            onClick={() => onDismiss && onDismiss(toast.id)}
            style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '0.9rem' }}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
