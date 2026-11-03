import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { LiveProcessPanel } from './LiveProcessPanel'
import type { TriageLifecycleEvent } from '@/types/execution'

describe('LiveProcessPanel', () => {
  it('renders initial standby state when events array is empty', () => {
    render(<LiveProcessPanel events={[]} isLoading={false} />)

    expect(screen.getByTestId('live-process-panel')).toBeInTheDocument()
    expect(screen.getByText('Standby')).toBeInTheDocument()
    expect(screen.getByText('0 of 9')).toBeInTheDocument()

    // Validation stage starts in Pending
    const valCard = screen.getByTestId('stage-card-validation')
    expect(valCard).toHaveTextContent('Pending')
  })

  it('renders running stage and active run indicator during execution', () => {
    const runningEvents: TriageLifecycleEvent[] = [
      {
        request_id: 'req-test',
        sequence: 1,
        timestamp: '2026-11-03T06:00:00Z',
        event_type: 'stage.started',
        stage: 'validation',
        status: 'running',
        safe_summary: 'Validating payload',
      },
    ]

    render(<LiveProcessPanel events={runningEvents} isLoading={true} />)

    expect(screen.getByText('Active Run')).toBeInTheDocument()
    const valCard = screen.getByTestId('stage-card-validation')
    expect(valCard).toHaveTextContent('Executing')
    expect(valCard).toHaveTextContent('Validating payload')
  })

  it('updates stage to Done upon stage.completed and displays safe summary', () => {
    const completedEvents: TriageLifecycleEvent[] = [
      {
        request_id: 'req-test',
        sequence: 1,
        timestamp: '2026-11-03T06:00:00Z',
        event_type: 'stage.completed',
        stage: 'validation',
        status: 'completed',
        safe_summary: 'Schema valid',
      },
      {
        request_id: 'req-test',
        sequence: 2,
        timestamp: '2026-11-03T06:00:01Z',
        event_type: 'stage.completed',
        stage: 'normalise',
        status: 'completed',
        safe_summary: 'Patient observations normalised',
      },
    ]

    render(<LiveProcessPanel events={completedEvents} isLoading={false} />)

    expect(screen.getByText('2 of 9')).toBeInTheDocument()
    const valCard = screen.getByTestId('stage-card-validation')
    expect(valCard).toHaveTextContent('Done')
    expect(valCard).toHaveTextContent('Schema valid')

    const normCard = screen.getByTestId('stage-card-normalise')
    expect(normCard).toHaveTextContent('Done')
    expect(normCard).toHaveTextContent('Patient observations normalised')
  })

  it('switches between Process Graph and Activity Feed tabs', () => {
    const events: TriageLifecycleEvent[] = [
      {
        request_id: 'req-test',
        sequence: 1,
        timestamp: '2026-11-03T06:00:00Z',
        event_type: 'stage.completed',
        stage: 'normalise',
        status: 'completed',
        safe_summary: 'Normalised safely',
      },
    ]

    render(<LiveProcessPanel events={events} isLoading={false} />)

    // Process Graph visible by default
    expect(screen.getByTestId('stage-card-normalise')).toBeInTheDocument()

    // Switch to feed
    const feedBtn = screen.getByRole('button', { name: /Activity Feed/i })
    fireEvent.click(feedBtn)

    // Feed event item rendered
    expect(screen.getByTestId('feed-event-item')).toBeInTheDocument()
    expect(screen.getByText('#01')).toBeInTheDocument()
    expect(screen.getByText('Normalised safely')).toBeInTheDocument()
  })

  it('displays skipped status for bypassed branches', () => {
    const skippedEvents: TriageLifecycleEvent[] = [
      {
        request_id: 'req-test',
        sequence: 1,
        timestamp: '2026-11-03T06:00:00Z',
        event_type: 'stage.skipped',
        stage: 'retrieve',
        status: 'skipped',
        safe_summary: 'Retrieval skipped by policy',
      },
    ]

    render(<LiveProcessPanel events={skippedEvents} isLoading={false} />)

    const retCard = screen.getByTestId('stage-card-retrieve')
    expect(retCard).toHaveTextContent('Skipped')
    expect(retCard).toHaveTextContent('Retrieval skipped by policy')
  })
})
