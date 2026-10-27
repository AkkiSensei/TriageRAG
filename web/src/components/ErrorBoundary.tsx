import { Component, ErrorInfo, ReactNode } from 'react'
import { AlertOctagon, RotateCcw } from 'lucide-react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('Unhandled UI exception caught by ErrorBoundary:', error, errorInfo)
  }

  private handleReset = (): void => {
    this.setState({ hasError: false, error: null })
    window.location.reload()
  }

  public render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-clinical-navy flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-clinical-surface border border-status-block/40 rounded-xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center space-x-3 text-status-block">
              <AlertOctagon className="w-8 h-8 flex-shrink-0" />
              <div>
                <h2 className="text-lg font-bold text-slate-100">Console Error Encountered</h2>
                <p className="text-xs text-status-block uppercase tracking-wider font-semibold">
                  Fail-Closed Safe Boundary
                </p>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              An unexpected interface exception occurred. Under fail-closed clinical safety
              standards, execution was halted to prevent rendering inconsistent clinical data.
            </p>

            {this.state.error && (
              <div className="bg-clinical-dark border border-clinical-border rounded p-3 text-xs font-mono text-status-block/90 overflow-x-auto">
                {this.state.error.message}
              </div>
            )}

            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={this.handleReset}
                className="inline-flex items-center space-x-2 px-4 py-2 bg-clinical-border hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Reload Console</span>
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
