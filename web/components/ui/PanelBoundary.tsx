"use client";

import { Component, type ReactNode } from "react";
import { StatusNote } from "./StatusNote";

/**
 * Per-panel React error boundary (spec §6): a render error in one module shows
 * a contained note and leaves the rest of the dashboard working. Combine with
 * useResource's error state for full isolation (fetch + render both covered).
 */
export class PanelBoundary extends Component<
  { children: ReactNode; label?: string },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <StatusNote
          tone="error"
          title="This panel could not render"
          message={`${this.props.label ?? "A module"} hit an error. The rest of the dashboard is unaffected.`}
        />
      );
    }
    return this.props.children;
  }
}
