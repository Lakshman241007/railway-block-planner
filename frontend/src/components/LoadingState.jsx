import React from 'react';

export default function LoadingState({ message = 'Loading operational telemetry...' }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '60px 20px',
        gap: 16,
      }}
    >
      <div className="radar-spinner" />
      <div style={{ color: '#94a3b8', fontSize: '0.85rem', fontWeight: 500, letterSpacing: '0.3px' }}>
        {message}
      </div>
    </div>
  );
}
