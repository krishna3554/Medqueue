/* eslint-disable no-unused-vars -- JSX-only imports flagged without the React plugin */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Intake } from '../components/Intake';

vi.mock('../api', () => ({
  createPatient: vi.fn(async () => ({ id: 9 })),
  createVisit: vi.fn(async () => ({ id: 77 })),
  extractSymptoms: vi.fn(async () => ({
    detected_language: 'hi',
    candidates: [
      { canonical: 'fever', confidence: 0.95, matched_text: 'bukhar', method: 'exact', negated: false, duration_days: 3 },
      { canonical: 'cough', confidence: 0.6, matched_text: 'khansi', method: 'fuzzy', negated: false, duration_days: null },
    ],
  })),
  saveSymptoms: vi.fn(async () => ({})),
  addVitals: vi.fn(async () => ({})),
}));

import { createPatient, createVisit, saveSymptoms } from '../api';

describe('Intake confirmation', () => {
  beforeEach(() => vi.clearAllMocks());

  it('extracts free text then confirms editable chips before saving', async () => {
    const complete = vi.fn();
    render(<Intake complete={complete} />);
    fireEvent.change(screen.getByLabelText(/Full name/), { target: { value: 'Synthetic Test' } });
    fireEvent.change(screen.getByLabelText(/Presenting complaint/), { target: { value: 'Fever and cough' } });
    fireEvent.change(screen.getByLabelText(/own words/), { target: { value: 'mujhe bukhar aur khansi hai' } });
    fireEvent.click(screen.getByText('Review symptoms'));
    await waitFor(() => expect(createVisit).toHaveBeenCalled());
    expect(await screen.findByText('Confirm symptoms')).toBeInTheDocument();
    expect(screen.getAllByText(/fever/).length).toBeGreaterThan(0);
    expect(screen.getByText(/cough.*check/)).toBeInTheDocument();
    fireEvent.click(screen.getByText('Confirm and add to queue'));
    await waitFor(() => expect(saveSymptoms).toHaveBeenCalledWith(77, ['fever', 'cough']));
    expect(createPatient).toHaveBeenCalledOnce();
    expect(complete).toHaveBeenCalledOnce();
  });
});
