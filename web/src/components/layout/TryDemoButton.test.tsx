import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { TryDemoButton } from './TryDemoButton'
import { IntakePage } from '@/pages/IntakePage'
import { TriageProvider, useTriage } from '@/context/TriageContext'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '@/lib/api'
import { createSyntheticDemoRequest, DEMO_DISCLAIMER } from '@/lib/demoPatient'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

describe('TryDemoButton Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
  })

  it('renders an accessible, responsive button fixed to the bottom-left', () => {
    render(
      <QueryClientProvider client={queryClient}>
        <TriageProvider>
          <MemoryRouter>
            <TryDemoButton />
          </MemoryRouter>
        </TriageProvider>
      </QueryClientProvider>
    )

    const button = screen.getByRole('button', { name: /try demo/i })
    expect(button).toBeDefined()

    // Accessible name or aria-label
    expect(button.getAttribute('aria-label')).toBe('Try Demo - Synthetic Patient Scenario')

    // Verify fixed positioning at bottom-left and safe area styling
    expect(button.className).toContain('fixed')
    expect(button.className).toContain('z-40')
    expect(button.className).toContain('left-4')
    expect(button.className).toContain('bottom-4')
    expect(button.style.left).toContain('env(safe-area-inset-left')
    expect(button.style.bottom).toContain('env(safe-area-inset-bottom')
  })

  it('navigates to /intake and sets demo active when clicked', () => {
    // Helper component to observe context changes
    const ContextObserver = () => {
      const { isDemoActive, patientRequest } = useTriage()
      return (
        <div>
          <div data-testid="is-demo">{isDemoActive ? 'yes' : 'no'}</div>
          <div data-testid="patient-age">{patientRequest?.patient.age.value || 'none'}</div>
        </div>
      )
    }

    render(
      <QueryClientProvider client={queryClient}>
        <TriageProvider>
          <MemoryRouter>
            <TryDemoButton />
            <ContextObserver />
          </MemoryRouter>
        </TriageProvider>
      </QueryClientProvider>
    )

    expect(screen.getByTestId('is-demo').textContent).toBe('no')
    expect(screen.getByTestId('patient-age').textContent).toBe('none')

    const button = screen.getByRole('button', { name: /try demo/i })
    fireEvent.click(button)

    expect(mockNavigate).toHaveBeenCalledWith('/intake')
    expect(screen.getByTestId('is-demo').textContent).toBe('yes')
    expect(screen.getByTestId('patient-age').textContent).toBe('58')
  })
})

describe('Synthetic Demo Patient Data & Safety Guarantees', () => {
  it('creates synthetic patient preserving unknown glucose and GCS', () => {
    const demo = createSyntheticDemoRequest()

    expect(demo.patient.age.value).toBe('58')
    expect(demo.patient.sex).toBe('male')
    expect(demo.patient.medications).toBeDefined()
    expect(demo.patient.medications!).toHaveLength(1)
    expect(demo.patient.medications![0].raw_text).toContain('Silagra')

    // Rule R2 & R4: Unknown is first-class, never silently defaulted to normal
    expect(demo.patient.vitals.blood_glucose_mg_dl?.value).toBeNull()
    expect(demo.patient.vitals.blood_glucose_mg_dl?.source).toBe('unknown')
    expect(demo.patient.vitals.gcs_total?.value).toBeNull()
    expect(demo.patient.vitals.gcs_total?.source).toBe('unknown')

    // Rule R7: Chief complaint is quarantined and untrusted
    expect(demo.include_complaint_in_llm).toBe(false)
  })
})

describe('Demo Patient Banner on IntakePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
  })

  it('displays the synthetic demo banner and disclaimer when demo is activated', () => {
    const TestApp = () => {
      const { loadDemoPatient } = useTriage()
      return (
        <div>
          <button type="button" onClick={loadDemoPatient}>
            Trigger Demo
          </button>
          <IntakePage />
        </div>
      )
    }

    render(
      <QueryClientProvider client={queryClient}>
        <TriageProvider>
          <MemoryRouter initialEntries={['/intake']}>
            <TestApp />
          </MemoryRouter>
        </TriageProvider>
      </QueryClientProvider>
    )

    // Initially no demo banner
    expect(screen.queryByTestId('demo-patient-banner')).toBeNull()

    // Trigger demo load
    fireEvent.click(screen.getByRole('button', { name: /trigger demo/i }))

    // Banner is visible
    const banner = screen.getByTestId('demo-patient-banner')
    expect(banner).toBeDefined()

    // Plain language contraindication explanation
    expect(banner.textContent).toContain('Synthetic Demo Patient Pre-filled')
    expect(banner.textContent).toContain('Expected Verdict: BLOCK')
    expect(banner.textContent).toContain('Rule R11')
    expect(banner.textContent).toContain('Code Decides; LLM Explains')

    // Verbatim disclaimer requirement
    expect(banner.textContent).toContain(DEMO_DISCLAIMER)

    // Form inputs should reflect demo patient
    const ageInput = screen.getByLabelText(/Age/i) as HTMLInputElement
    expect(ageInput.value).toBe('58')

    // Resetting/clearing demo restores blank state
    const clearBtn = screen.getByRole('button', { name: /clear demo \/ reset/i })
    fireEvent.click(clearBtn)

    expect(screen.queryByTestId('demo-patient-banner')).toBeNull()
  })
})
