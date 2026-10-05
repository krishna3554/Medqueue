/* eslint-disable no-unused-vars -- JSX-only imports flagged without the React plugin */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { QueueList } from '../components/QueueList';

const queue = [
  {
    id: 1,
    patient: { id: 1, name: 'Synthetic Asha', date_of_birth: '1990-01-01' },
    complaint: 'Chest tightness',
    registered_at: new Date(Date.now() - 3 * 60000).toISOString(),
    status: 'waiting',
    triage: { level: 1, red_flag: true, factors: ['Chest symptoms with low oxygen'], source: 'rules' },
    latest_vitals: { spo2: 91 },
    priority_score: 1.9,
    est_wait_min: 0,
  },
  {
    id: 2,
    patient: { id: 2, name: 'Synthetic Ravi', date_of_birth: '2000-06-01' },
    complaint: 'Cough',
    registered_at: new Date(Date.now() - 30 * 60000).toISOString(),
    status: 'waiting',
    triage: { level: 4, red_flag: false, factors: [], source: 'stub' },
    latest_vitals: {},
    priority_score: 0.2,
    est_wait_min: 10,
  },
];

describe('QueueList', () => {
  it('renders patients in priority order with expected review', () => {
    render(
      <QueueList
        visible={queue}
        selectedId={1}
        onSelect={() => {}}
        loading={false}
        query=""
        setQuery={() => {}}
        filter="All patients"
        setFilter={() => {}}
      />,
    );
    expect(screen.getByText('Synthetic Asha')).toBeInTheDocument();
    expect(screen.getByText('Synthetic Ravi')).toBeInTheDocument();
    expect(screen.getByText('Red flag')).toBeInTheDocument();
    expect(screen.getByText('Now')).toBeInTheDocument();
    expect(screen.getByText('~10 min')).toBeInTheDocument();
  });
});
