import { AIAgentWidget } from './ui/ai-agent-widget'

/**
 * Route-independent assistant launcher.
 *
 * Kept at the end of the application shell so the Ask ClaimLens button stays
 * available on every workspace page after navigation, but not on the hero.
 */
export function ClaimAssistant() {
  if ((window.location.pathname.replace(/\/+$/, '') || '/') === '/') return null
  return <AIAgentWidget />
}

export default ClaimAssistant
