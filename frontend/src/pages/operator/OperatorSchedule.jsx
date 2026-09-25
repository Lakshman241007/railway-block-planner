import React from 'react';
import Schedule from '../Schedule';

export default function OperatorSchedule(props) {
  return <Schedule {...props} isOperator={true} />;
}
