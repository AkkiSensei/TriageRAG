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
        <div className="min-h-screen bg-[#F4F6F4] flex items-center justify-center p-6 text-[#1A2421]">
          <div className="max-w-md w-full bg-white border border-[#E1E7E1] rounded-2xl p-6 shadow-xl space-y-4">
            <div className="flex items-center space-x-3 text-red-600">
              <AlertOctagon className="w-8 h-8 flex-shrink-0" />
              <div>
                <h2 className="text-lg font-bold text-[#1A2421]">Console Error Encountered</h2>
                <p className="text-xs text-red-700 uppercase tracking-wider font-bold">
                  Fail-Closed Safe Boundary
                </p>
              </div>
            </div>

            <p className="text-xs text-[#5C6B64] leading-relaxed">
              An unexpected interface exception occurred. Under fail-closed clinical safety
              standards, execution was halted to prevent rendering inconsistent clinical data.
            </p>

            {this.state.error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-xs font-mono text-red-900 overflow-x-auto">
                {this.state.error.message}
              </div>
            )}

            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={this.handleReset}
                className="inline-flex items-center space-x-2 px-4 py-2 bg-[#2D6A4F] hover:bg-[#1B4D39] text-white text-xs font-bold rounded-lg transition-colors shadow-xs"
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
