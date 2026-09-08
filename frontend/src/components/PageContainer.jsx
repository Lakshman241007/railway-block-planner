import React from 'react';

export default function PageContainer({ children, className = '' }) {
  return (
    <div className={`page-container ${className}`}>
      {children}
    </div>
  );
}
