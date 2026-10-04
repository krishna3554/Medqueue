/* eslint-disable no-unused-vars -- JSX-only imports flagged without the React plugin */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { OverrideModal } from '../components/OverrideModal';

function Harness({ onSubmit, onClose }) {
  const [level, setLevel] = useState(3);
  const [reason, setReason] = useState('');
  return (
    <OverrideModal
      level={level}
      setLevel={setLevel}
      reason={reason}
      setReason={setReason}
      onSubmit={onSubmit}
      onClose={onClose}
    />
  );
}

describe('OverrideModal', () => {
  it('submits the chosen level and reason', () => {
    const onSubmit = vi.fn((e) => e.preventDefault());
    const onClose = vi.fn();
    render(<Harness onSubmit={onSubmit} onClose={onClose} />);
    fireEvent.change(screen.getByLabelText(/Urgency level/), { target: { value: '1' } });
    expect(screen.getByLabelText(/Urgency level/).value).toBe('1');
    fireEvent.change(screen.getByLabelText(/Override reason/), { target: { value: 'Clinician reassessment' } });
    fireEvent.click(screen.getByText('Save override'));
    expect(onSubmit).toHaveBeenCalledOnce();
  });
});
