import React from 'react';
import Maintenance from '../Maintenance';

export default function OperatorMaintenance(props) {
  return <Maintenance {...props} isOperator={true} />;
}
