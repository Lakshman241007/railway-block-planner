import React from 'react';
import Trains from '../Trains';

export default function OperatorTrains(props) {
  return <Trains {...props} isOperator={true} />;
}
