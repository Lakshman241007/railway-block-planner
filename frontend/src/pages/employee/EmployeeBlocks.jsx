import React, { useState } from 'react';
import PageContainer from '../../components/PageContainer';
import BlockTable from '../../components/BlockTable';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

export default function EmployeeBlocks({
  blocks = [],
  loading = false,
  error = null,
  onRetry,
  onSelectBlock,
}) {
  return (
    <PageContainer>
      {/* Employee Awareness Banner */}
      <div className="employee-info-banner">
        <div className="employee-banner-icon">🚧</div>
        <div className="employee-banner-content">
          <div className="employee-banner-title">
            BDMS Block & Disconnection Status (Read-Only)
          </div>
          <div className="employee-banner-subtitle">
            Live directory of approved and requested maintenance possessions from the Block Disconnection Management System. Click any row to inspect details.
          </div>
        </div>
        <div className="employee-banner-tag">
          {blocks.length} RECORDS
        </div>
      </div>

      {error ? (
        <ErrorState
          title="Failed to Load Block Records"
          message={error}
          onRetry={onRetry}
        />
      ) : loading ? (
        <LoadingState message="Fetching BDMS block records..." />
      ) : (
        <BlockTable
          blocks={blocks}
          title="Official BDMS Disconnection Records"
          subtitle="Unified Block Disconnection Management System — Employee Inspection View"
          onSelectBlock={onSelectBlock}
          showFilters={true}
          headerAction={null} /* Strictly NO submit button for employee */
        />
      )}
    </PageContainer>
  );
}
