import React, { useState } from 'react';
import TrainCard from '../components/TrainCard';
import LoadingState from '../components/LoadingState';

export default function Trains({ trains = [], loading = false }) {
  const [filterType, setFilterType] = useState('ALL');
  const [search, setSearch] = useState('');

  const filtered = trains.filter((t) => {
    const isGoods = String(t.train_type || '').toLowerCase().includes('freight') ||
                    String(t.train_type || '').toLowerCase().includes('goods') ||
                    String(t.train_id || '').startsWith('G');

    if (filterType === 'PASSENGER' && isGoods) return false;
    if (filterType === 'GOODS' && !isGoods) return false;

    if (search) {
      const match = (t.train_id && t.train_id.toLowerCase().includes(search.toLowerCase())) ||
                    (t.train_name && t.train_name.toLowerCase().includes(search.toLowerCase())) ||
                    (t.origin && t.origin.toLowerCase().includes(search.toLowerCase())) ||
                    (t.destination && t.destination.toLowerCase().includes(search.toLowerCase()));
      if (!match) return false;
    }

    return true;
  });

  const passengerCount = trains.filter((t) => !String(t.train_type || '').toLowerCase().includes('goods') && !String(t.train_id || '').startsWith('G')).length;
  const goodsCount = trains.length - passengerCount;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>🚦 Corridor Train Traffic Monitoring</span>
              <span className="badge badge-cyan">{trains.length} SERVICES</span>
            </div>
            <div className="panel-subtitle">
              Live timetable schedules and active train movements (TMS / COA)
            </div>
          </div>

          <div style={{ display: 'flex', gap: 10 }}>
            <button
              className={`btn btn-sm ${filterType === 'ALL' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setFilterType('ALL')}
            >
              All ({trains.length})
            </button>
            <button
              className={`btn btn-sm ${filterType === 'PASSENGER' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setFilterType('PASSENGER')}
            >
              🚆 Passenger ({passengerCount})
            </button>
            <button
              className={`btn btn-sm ${filterType === 'GOODS' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setFilterType('GOODS')}
            >
              📦 Goods / Freight ({goodsCount})
            </button>
          </div>
        </div>

        <div className="panel-body">
          <div className="filter-toolbar">
            <div className="search-input-wrap">
              <span className="search-icon">🔍</span>
              <input
                type="text"
                className="search-input"
                placeholder="Search Train Number, Station, Name..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>

          {loading ? (
            <LoadingState message="Connecting to train movement stream..." />
          ) : filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
              No trains found matching the selected filter.
            </div>
          ) : (
            <div className="card-grid">
              {filtered.map((train, idx) => (
                <TrainCard key={train.train_id + idx} train={train} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
