import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { RetrievalView } from './RetrievalView'
import type { TriageResponse } from '@/lib/api'

const createMockTriage = (overrides?: Partial<TriageResponse>): TriageResponse => {
  return {
    engine: {
      verdict: 'CHECKED_CLEAR',
      checks_run: 10,
      checks_skipped: [],
      baseline_alerts: [],
      plan_alerts: [],
    },
    retrieval: {
      chunks: [
        {
          chunk_id: 'CHUNK_01',
          doc_id: 'SYNTH_ANAPHYLAXIS_01',
          section: 'Section 1: Initial Assessment',
          text: 'Administer epinephrine 0.5 mg IM immediately into anterolateral thigh.',
          score: 12.5,
        },
        {
          chunk_id: 'CHUNK_02',
          doc_id: 'SYNTH_ANAPHYLAXIS_01',
          section: 'Section 2: Adjunctive Therapy',
          text: 'Establish high-flow oxygen and intravenous fluid resuscitation.',
          score: 9.8,
        },
      ],
      backend: 'bm25',
      abstained: false,
      abstain_code: 'NONE',
      reason: null,
      query: 'epinephrine anaphylaxis',
      filters: { population: 'adult', syndrome: 'anaphylaxis' },
      corpus_hash: 'abc123456789deadbeef',
    },
    retrieved_protocol_title: 'Adult Anaphylaxis Management',
    llm_fallback_mode: false,
    ...overrides,
  } as TriageResponse
}

describe('RetrievalView Component Tests', () => {
  it('returns null if neither retrieval nor protocolTitle is provided', () => {
    const mock = { engine: { verdict: 'CHECKED_CLEAR' } } as unknown as TriageResponse
    const { container } = render(<RetrievalView triage={mock} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders protocol title and chunk count toggle button', () => {
    const mock = createMockTriage()
    render(<RetrievalView triage={mock} />)

    expect(screen.getByText('Adult Anaphylaxis Management')).toBeInTheDocument()
    expect(screen.getByText('2 Chunks')).toBeInTheDocument()
  })

  it('renders chunks and allows collapsing chunk drawer', () => {
    const mock = createMockTriage()
    render(<RetrievalView triage={mock} />)

    expect(screen.getByText(/Section 1: Initial Assessment/i)).toBeInTheDocument()
    expect(screen.getByText(/Administer epinephrine 0.5 mg IM immediately/i)).toBeInTheDocument()

    // Collapse drawer
    const toggleButton = screen.getByRole('button', { name: /2 Chunks/i })
    fireEvent.click(toggleButton)
    expect(screen.queryByText(/Section 1: Initial Assessment/i)).not.toBeInTheDocument()
  })

  it('renders abstention banner when retrieval is abstained with NO_POPULATION_COVERAGE', () => {
    const mock = createMockTriage({
      retrieval: {
        chunks: [],
        backend: 'bm25',
        abstained: true,
        abstain_code: 'NO_POPULATION_COVERAGE',
        reason: "No verified protocol chunks available for population 'neonatal'",
        query: 'epinephrine neonatal',
        filters: { population: 'neonatal' },
      },
      retrieved_protocol_title: undefined,
    })

    render(<RetrievalView triage={mock} />)

    expect(screen.getByText(/Retrieval Abstained/i)).toBeInTheDocument()
    expect(screen.getByText(/Gate: NO_POPULATION_COVERAGE/i)).toBeInTheDocument()
    expect(screen.getByText(/No verified protocol chunks available for population 'neonatal'/i)).toBeInTheDocument()
  })

  it('renders abstention banner with NO_RESULTS code', () => {
    const mock = createMockTriage({
      retrieval: {
        chunks: [],
        backend: 'bm25',
        abstained: true,
        abstain_code: 'NO_RESULTS',
        reason: "No protocol chunks matched retrieval query for population 'adult'",
        query: 'unmatched query text',
        filters: { population: 'adult' },
      },
    })

    render(<RetrievalView triage={mock} />)

    expect(screen.getByText(/Gate: NO_RESULTS/i)).toBeInTheDocument()
    expect(screen.getByText(/No protocol chunks matched retrieval query/i)).toBeInTheDocument()
  })

  it('renders abstention banner with LOW_CONFIDENCE code', () => {
    const mock = createMockTriage({
      retrieval: {
        chunks: [],
        backend: 'bm25',
        abstained: true,
        abstain_code: 'LOW_CONFIDENCE',
        reason: 'Top retrieval relevance is below calibrated threshold 0.15',
        query: 'vague symptom',
        filters: { population: 'adult' },
      },
    })

    render(<RetrievalView triage={mock} />)

    expect(screen.getByText(/Gate: LOW_CONFIDENCE/i)).toBeInTheDocument()
    expect(screen.getByText(/below calibrated threshold/i)).toBeInTheDocument()
  })

  it('renders fallback mode notice when llm_fallback_mode is active', () => {
    const mock = createMockTriage({ llm_fallback_mode: true })
    render(<RetrievalView triage={mock} />)

    expect(screen.getByText(/Plan Drafting Skipped \(Fallback Mode Active\)/i)).toBeInTheDocument()
  })

  it('toggles "How Retrieval Worked" informational drawer', () => {
    const mock = createMockTriage()
    render(<RetrievalView triage={mock} />)

    const howButton = screen.getByRole('button', { name: /How Retrieval Worked/i })
    expect(screen.queryByText(/Retrieval Mechanics & Gating Architecture/i)).not.toBeInTheDocument()

    fireEvent.click(howButton)
    expect(screen.getByText(/Retrieval Mechanics & Gating Architecture/i)).toBeInTheDocument()
    expect(screen.getByText(/epinephrine anaphylaxis/i)).toBeInTheDocument()
  })
})
