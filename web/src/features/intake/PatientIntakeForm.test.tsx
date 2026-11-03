import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PatientIntakeForm } from './PatientIntakeForm'
import type { TriageApiRequest } from '@/lib/api'

describe('PatientIntakeForm Data Propagation', () => {
  it('correctly maps entered weight to measured status in submitted payload', () => {
    let submittedPayload: TriageApiRequest | null = null
    const handleSubmit = vi.fn((payload: TriageApiRequest) => {
      submittedPayload = payload
    })

    render(<PatientIntakeForm onSubmit={handleSubmit} />)

    // Find weight input and enter a known value
    const weightInput = screen.getByPlaceholderText('82.0') as HTMLInputElement
    fireEvent.change(weightInput, { target: { value: '74.5' } })

    // Submit form
    const submitBtn = screen.getByRole('button', { name: /Check Safety & View Care Steps/i })
    fireEvent.click(submitBtn)

    expect(handleSubmit).toHaveBeenCalledOnce()
    expect(submittedPayload).not.toBeNull()
    expect(submittedPayload!.patient.weight_kg.value).toBe('74.5')
    expect(submittedPayload!.patient.weight_kg.source).toBe('measured')
  })

  it('preserves genuine unknown weight when left blank', () => {
    let submittedPayload: TriageApiRequest | null = null
    const handleSubmit = vi.fn((payload: TriageApiRequest) => {
      submittedPayload = payload
    })

    render(<PatientIntakeForm onSubmit={handleSubmit} />)

    const weightInput = screen.getByPlaceholderText('82.0') as HTMLInputElement
    fireEvent.change(weightInput, { target: { value: '' } })

    const submitBtn = screen.getByRole('button', { name: /Check Safety & View Care Steps/i })
    fireEvent.click(submitBtn)

    expect(handleSubmit).toHaveBeenCalledOnce()
    expect(submittedPayload!.patient.weight_kg.value).toBeNull()
    expect(submittedPayload!.patient.weight_kg.source).toBe('unknown')
  })

  it('correctly maps supplemental oxygen and consciousness to measured payload', () => {
    let submittedPayload: TriageApiRequest | null = null
    const handleSubmit = vi.fn((payload: TriageApiRequest) => {
      submittedPayload = payload
    })

    render(<PatientIntakeForm onSubmit={handleSubmit} />)

    // Select supplemental oxygen "yes"
    const o2Select = screen.getByDisplayValue(/Normal room air/i)
    fireEvent.change(o2Select, { target: { value: 'yes' } })

    // Select consciousness "New Confusion"
    const consciousnessSelect = screen.getByDisplayValue(/Alert - Fully awake/i)
    fireEvent.change(consciousnessSelect, { target: { value: 'C' } })

    const submitBtn = screen.getByRole('button', { name: /Check Safety & View Care Steps/i })
    fireEvent.click(submitBtn)

    expect(handleSubmit).toHaveBeenCalledOnce()
    const vitals = submittedPayload!.patient.vitals
    expect(vitals.supplemental_o2?.value).toBe('yes')
    expect(vitals.supplemental_o2?.source).toBe('measured')
    expect(vitals.consciousness?.value).toBe('C')
    expect(vitals.consciousness?.source).toBe('measured')
  })

  it('submits exactly once on click and inhibits duplicate submission while loading', () => {
    const handleSubmit = vi.fn()
    const { rerender } = render(<PatientIntakeForm onSubmit={handleSubmit} isLoading={false} />)

    const submitBtn = screen.getByRole('button', { name: /Check Safety & View Care Steps/i })
    fireEvent.click(submitBtn)

    expect(handleSubmit).toHaveBeenCalledTimes(1)

    // Re-render in loading state
    rerender(<PatientIntakeForm onSubmit={handleSubmit} isLoading={true} />)
    const loadingBtn = screen.getByRole('button', { name: /Checking safety rules\.\.\./i })
    expect(loadingBtn).toBeDisabled()
    fireEvent.click(loadingBtn)

    // Still only called once!
    expect(handleSubmit).toHaveBeenCalledTimes(1)
  })
})
