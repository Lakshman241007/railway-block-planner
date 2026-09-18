import React, { useState } from 'react';
import PageContainer from '../components/PageContainer';
import TrainCard from '../components/TrainCard';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';

export default function Trains({ trains = [], movements = [], loading = false, error = null, onRetry }) {
  const [activeTab, setActiveTab] = useState('trains'); // 'trains' | 'movements'
  const [filterType, setFilterType] = useState('ALL');
  const [search, setSearch] = useState('');

  const filteredTrains = trains.filter((t) => {
    const isGoods = String(t.train_type || '').toLowerCase().includes('freight') ||
                    String(t.train_type || '').toLowerCase().includes('goods') ||
                    String(t.train_id || '').startsWith('G');

    if (filterType === 'PASSENGER' && isGoods) return false;
    if (filterType === 'GOODS' && !isGoods) return false;

    if (search) {
      const match = (t.train_id && t.train_id.toLowerCase().includes(search.toLowerCase())) ||
                    (t.origin && t.origin.toLowerCase().includes(search.toLowerCase())) ||
                    (t.destination && t.destination.toLowerCase().includes(search.toLowerCase()));
      if (!match) return false;
    }

    return true;
  });

  const filteredMovements = movements.filter((m) => {
    if (!search) return true;
    return (m.train_id && m.train_id.toLowerCase().includes(search.toLowerCase())) ||
           (m.section && m.section.toLowerCase().includes(search.toLowerCase())) ||
           (m.route_id && m.route_id.toLowerCase().includes(search.toLowerCase()));
  });

  const passengerCount = trains.filter((t) => !String(t.train_type || '').toLowerCase().includes('goods') && !String(t.train_id || '').startsWith('G')).length;
  const goodsCount = trains.length - passengerCount;

  return (
    <PageContainer>
      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>🚦 Corridor Train Traffic & Occupancy</span>
              <span className="badge badge-cyan">{trains.length} TRAINS</span>
              <span className="badge badge-outline">{movements.length} MOVEMENTS</span>
            </div>
            <div className="panel-subtitle">
              Live timetable schedules and active corridor section occupancies (TMS / TDMS / COA)
            </div>
          </div>

          <div className="segmented-control">
            <button
              className={`segmented-tab ${activeTab === 'trains' ? 'active' : ''}`}
              onClick={() => setActiveTab('trains')}
            >
              🚆 Trains ({trains.length})
            </button>
            <button
              className={`segmented-tab ${activeTab === 'movements' ? 'active' : ''}`}
              onClick={() => setActiveTab('movements')}
            >
              📍 COA Section Movements ({movements.length})
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
                placeholder={activeTab === 'trains' ? "Search Train ID, Origin, Destination..." : "Search Train ID, Section, Route..."}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            {activeTab === 'trains' && (
              <div className="segmented-control">
                <button
                  className={`segmented-tab ${filterType === 'ALL' ? 'active' : ''}`}
                  onClick={() => setFilterType('ALL')}
                >
                  All ({trains.length})
                </button>
                <button
                  className={`segmented-tab ${filterType === 'PASSENGER' ? 'active' : ''}`}
                  onClick={() => setFilterType('PASSENGER')}
                >
                  Passenger ({passengerCount})
                </button>
                <button
                  className={`segmented-tab ${filterType === 'GOODS' ? 'active' : ''}`}
                  onClick={() => setFilterType('GOODS')}
                >
                  Goods ({goodsCount})
                </button>
              </div>
            )}
          </div>

          {error ? (
            <ErrorState
              title="Failed to Load Traffic Data"
              message={error}
              onRetry={onRetry}
            />
          ) : loading ? (
            <LoadingState message="Connecting to train traffic telemetry stream..." />
          ) : activeTab === 'trains' ? (
            filteredTrains.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
                No trains found matching the selected filter.
              </div>
            ) : (
              <div className="card-grid">
                {filteredTrains.map((train, idx) => (
                  <TrainCard key={train.train_id + idx} train={train} />
                ))}
              </div>
            )
          ) : (
            /* Movements Table */
            <div className="table-responsive">
              <table className="table">
                <thead>
                  <tr>
                    <th>Train ID</th>
                    <th>Route ID</th>
                    <th>Corridor Section</th>
                    <th>Direction</th>
                    <th>Movement Status</th>
                    <th>Entry Time</th>
                    <th>Exit Time</th>
                    <th>Track Line</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredMovements.length === 0 ? (
                    <tr>
                      <td colSpan="9" style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
                        No corridor movement records available.
                      </td>
                    </tr>
                  ) : (
                    filteredMovements.map((mov, idx) => (
                      <tr key={(mov.train_id || 'MOV') + idx}>
                        <td className="table-cell-mono" style={{ fontWeight: 700, color: '#38bdf8' }}>
                          {mov.train_id}
                        </td>
                        <td className="table-cell-mono">{mov.route_id}</td>
                        <td className="table-cell-highlight">{mov.section}</td>
                        <td>
                          <span className={`badge ${mov.direction === 'Up' ? 'badge-cyan' : 'badge-outline'}`}>
                            {mov.direction}
                          </span>
                        </td>
                        <td>
                          <span className={`badge ${
                            mov.movement_status === 'Occupied' ? 'badge-critical' :
                            mov.movement_status === 'Approaching' ? 'badge-high' : 'badge-info'
                          }`}>
                            {mov.movement_status}
                          </span>
                        </td>
                        <td className="table-cell-mono" style={{ color: '#34d399' }}>{mov.entry_time}</td>
                        <td className="table-cell-mono" style={{ color: '#34d399' }}>{mov.exit_time}</td>
                        <td className="table-cell-mono">{mov.line}</td>
                        <td>
                          <span className="badge badge-outline">{mov.source || 'COA'}</span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
