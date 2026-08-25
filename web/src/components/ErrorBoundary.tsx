import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

// A render crash shouldn't blank the whole app to a silent white screen --
// this catches it and shows a minimal message. Distinct from the map's own
// fail-silent behavior on data-fetch failures: this only covers actual
// render bugs, not "no data available."
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Uncaught render error:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: '2rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
          <h1>Something broke</h1>
          <p>{this.state.error.message}</p>
        </div>
      )
    }
    return this.props.children
  }
}
