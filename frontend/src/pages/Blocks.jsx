import React from 'react';
import BlockTable from '../components/BlockTable';
import LoadingState from '../components/LoadingState';

export default function Blocks({ blocks = [], loading = false, onSelectBlock }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {loading ? (
        <LoadingState message="Fetching BDMS block requests..." />
      ) : (
        <BlockTable
          blocks={blocks}
          title="BDMS Block & Disconnection Requests"
          subtitle="Unified Block Disconnection Management System database records"
          onSelectBlock={onSelectBlock}
          showFilters={true}
        />
      )}
    </div>
  );
}
