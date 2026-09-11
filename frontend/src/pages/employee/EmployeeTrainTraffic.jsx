import React, { useState } from 'react';
import PageContainer from '../../components/PageContainer';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

export default function EmployeeTrainTraffic({
  trains = [],
  movements = [],
  loading = false,
  error = null,
  onRetry,
}) {
  const [activeTab, setActiveTab] = useState('trains'); // 'trains' | 'movements'
  const [filterType, setFilterType] = useState('ALL');
  const [search, setSearch] = useState('');

  const filteredTrains = trains.filter((t) => {
    const isGoods =
      String(t.train_type || '').toLowerCase().includes('freight') ||
      String(t.train_type || '').toLowerCase().includes('goods') ||
      String(t.train_id || '').startsWith('G');

    if (filterType === 'PASSENGER' && isGoods) return false;
    if (filterType === 'GOODS' && !isGoods) return false;

    if (search) {
      const match =
        (t.train_id && t.train_id.toLowerCase().includes(search.toLowerCase())) ||
        (t.origin && t.origin.toLowerCase().includes(search.toLowerCase())) ||
        (t.destination && t.destination.toLowerCase().includes(search.toLowerCase()));
      if (!match) return false;
    }

    return true;
  });

  const filteredMovements = movements.filter((m) => {
    if (!search) return true;
    return (
      (m.train_id && m.train_id.toLowerCase().includes(search.toLowerCase())) ||
      (m.section && m.section.toLowerCase().includes(search.toLowerCase())) ||
      (m.route_id && m.route_id.toLowerCase().includes(search.toLowerCase()))
    );
  });

  const passengerCount = trains.filter(
    (t) =>
      !String(t.train_type || '').toLowerCase().includes('goods') &&
      !String(t.train_id || '').startsWith('G')
  ).length;
  const goodsCount = trains.length - passengerCount;

  return (
    <PageContainer>
      {/* Employee Awareness Banner */}
      <div className="employee-info-banner">
        <div className="employee-banner-icon">🚦</div>
        <div className="employee-banner-content">
          <div className="employee-banner-title">
            Corridor Train Traffic & Section Occupancy (Read-Only)
          </div>
          <div className="employee-banner-subtitle">
            Real-time feed of timetabled passenger services and freight transit corridors from TMS / TDMS / COA telemetry.
          </div>
        </div>
        <div className="employee-banner-tag">
          {trains.length} TRAINS ACTIVE
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <span>🚦 Corridor Train Traffic & Occupancy</span>
              <span className="badge badge-green">{trains.length} TRAINS</span>
              <span className="badge badge-outline">{movements.length} MOVEMENTS</span>
            </div>
            <div className="panel-subtitle">
              Live timetable schedules and active corridor section occupancies
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
                placeholder={
                  activeTab === 'trains'
                    ? 'Search Train ID, Origin, Destination...'
                    : 'Search Train ID, Section, Route...'
                }
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
                  Goods / Freight ({goodsCount})
                </button>
              </div>
            )}
          </div>

          {error ? (
            <ErrorState
              title="Failed to Load Train Traffic"
              message={error}
              onRetry={onRetry}
            />
          ) : loading ? (
            <LoadingState message="Connecting to train telemetry feeds..." />
          ) : activeTab === 'trains' ? (
            <div className="table-responsive">
              <table className="table">
                <thead>
                  <tr>
                    <th>Train ID</th>
                    <th>Type</th>
                    <th>Origin</th>
                    <th>Destination</th>
                    <th>Departure</th>
                    <th>Arrival</th>
                    <th>Speed (km/h)</th>
                    <th>Length</th>
                    <th>Priority</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTrains.length === 0 ? (
                    <tr>
                      <td colSpan="9" style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
                        No trains found matching criteria.
                      </td>
                    </tr>
                  ) : (
                    filteredTrains.map((t, idx) => (
                      <tr key={t.train_id + idx}>
                        <td className="table-cell-mono" style={{ fontWeight: 700, color: '#38bdf8' }}>
                          {t.train_id}
                        </td>
                        <td>
                          <span
                            className={`badge ${
                              String(t.train_type || '').toLowerCase().includes('freight') ||
                              String(t.train_type || '').toLowerCase().includes('goods')
                                ? 'badge-warning'
                                : 'badge-cyan'
                            }`}
                          >
                            {t.train_type || 'Passenger'}
                          </span>
                        </td>
                        <td className="table-cell-highlight">{t.origin}</td>
                        <td className="table-cell-highlight">{t.destination}</td>
                        <td className="table-cell-mono" style={{ color: '#34d399' }}>{t.departure_time || '--:--'}</td>
                        <td className="table-cell-mono" style={{ color: '#34d399' }}>{t.arrival_time || '--:--'}</td>
                        <td className="table-cell-mono">{t.max_speed || 110} km/h</td>
                        <td className="table-cell-mono">{t.length_meters ? `${t.length_meters}m` : '24 Coaches'}</td>
                        <td>
                          <span className="badge badge-outline">P{t.priority_score ?? 1}</span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            /* Movements tab */
            <div className="table-responsive">
              <table className="table">
                <thead>
                  <tr>
                    <th>Train ID</th>
                    <th>Section</th>
                    <th>Route ID</th>
                    <th>Entry Time</th>
                    <th>Exit Time</th>
                    <th>Direction</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredMovements.length === 0 ? (
                    <tr>
                      <td colSpan="6" style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>
                        No COA section movements recorded.
                      </td>
                    </tr>
                  ) : (
                    filteredMovements.map((m, idx) => (
                      <tr key={(m.train_id || 'M') + idx}>
                        <td className="table-cell-mono" style={{ fontWeight: 700, color: '#38bdf8' }}>
                          {m.train_id}
                        </td>
                        <td className="table-cell-highlight">{m.section}</td>
                        <td className="table-cell-mono">{m.route_id}</td>
                        <td className="table-cell-mono" style={{ color: '#34d399' }}>{m.entry_time || '--:--'}</td>
                        <td className="table-cell-mono" style={{ color: '#34d399' }}>{m.exit_time || '--:--'}</td>
                        <td>
                          <span className="badge badge-outline">{m.direction || 'UP'}</span>
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
