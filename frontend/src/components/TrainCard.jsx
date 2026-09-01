import React from 'react';
import StatusBadge from './StatusBadge';

export default function TrainCard({ train, onClick }) {
  const isGoods = String(train.train_type || '').toLowerCase().includes('freight') ||
                  String(train.train_type || '').toLowerCase().includes('goods') ||
                  String(train.train_id || '').startsWith('G');

  const delayMins = train.delay_minutes || 0;

  return (
    <div
      className="operation-card clickable"
      onClick={() => onClick && onClick(train)}
      style={{
        borderTop: isGoods ? '3px solid #f59e0b' : '3px solid #38bdf8',
      }}
    >
      <div className="card-header-row">
        <div>
          <div className="card-code" style={{ color: isGoods ? '#fbbf24' : '#38bdf8' }}>
            {isGoods ? '📦' : '🚆'} {train.train_id}
          </div>
          <div className="card-meta-text">{train.train_name || (isGoods ? 'Goods Freight Service' : 'Express Passenger')}</div>
        </div>
        <StatusBadge status={train.status || 'Running'} />
      </div>

      <div className="card-detail-box">
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#94a3b8' }}>Type:</span>
          <span className={`badge ${isGoods ? 'badge-high' : 'badge-info'}`}>
            {isGoods ? 'GOODS / FREIGHT' : 'PASSENGER'}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#94a3b8' }}>Route:</span>
          <span style={{ color: '#fff', fontWeight: 600 }}>{train.origin || 'Origin'} ➔ {train.destination || 'Destination'}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#94a3b8' }}>Schedule:</span>
          <span className="table-cell-mono">{train.departure_time || train.scheduled_time || '08:00'}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#94a3b8' }}>Delay / Variance:</span>
          <span style={{ color: delayMins > 10 ? '#ef4444' : '#10b981', fontFamily: 'var(--font-mono)' }}>
            {delayMins > 0 ? `+${delayMins} min` : 'On Time'}
          </span>
        </div>
      </div>
    </div>
  );
}
