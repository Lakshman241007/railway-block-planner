import React from 'react';
import Forecast from '../Forecast';

export default function OperatorForecast(props) {
  return <Forecast {...props} isOperator={true} />;
}
