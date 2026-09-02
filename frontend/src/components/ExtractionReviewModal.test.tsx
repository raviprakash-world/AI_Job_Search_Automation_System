import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ExtractionReviewModal from './ExtractionReviewModal'
import type { ProfileExtraction } from '../api/types'

const extraction: ProfileExtraction = {
  id: 'extraction-1',
  document_id: 'doc-1',
  status: 'pending',
  extracted_data: {},
  conflicts: [
    {
      change_id: 'field:full_name',
      kind: 'field_update',
      field: 'full_name',
      existing_value: null,
      proposed_value: 'Jane Doe',
    },
    {
      change_id: 'experience:0',
      kind: 'new_experience',
      existing_value: null,
      proposed_value: { company: 'Acme Corp', title: 'Engineer' },
    },
  ],
}

describe('ExtractionReviewModal', () => {
  it('renders every pending change and disables submit until a decision is made', () => {
    render(<ExtractionReviewModal extraction={extraction} onSubmit={vi.fn()} onClose={vi.fn()} />)

    expect(screen.getByTestId('change-field:full_name')).toBeInTheDocument()
    expect(screen.getByTestId('change-experience:0')).toBeInTheDocument()
    expect(screen.getByText('0 of 2 decided')).toBeInTheDocument()
    expect(screen.getByText('Apply decisions')).toBeDisabled()
  })

  it('only submits changes that were explicitly accepted or rejected', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<ExtractionReviewModal extraction={extraction} onSubmit={onSubmit} onClose={vi.fn()} />)

    const nameCard = screen.getByTestId('change-field:full_name')
    fireEvent.click(within(nameCard).getByText('Accept'))

    expect(screen.getByText('1 of 2 decided')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Apply decisions'))

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith([{ change_id: 'field:full_name', action: 'accept' }]))
  })
})
