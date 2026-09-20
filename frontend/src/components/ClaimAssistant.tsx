import { AIAgentWidget } from './ui/ai-agent-widget'

/**
 * Route-independent assistant launcher.
 *
 * Kept at the end of the application shell so the Ask ClaimLens button stays
 * available on the hero and on every workspace page after navigation.
 */
export function ClaimAssistant() {
  return <AIAgentWidget />
}

export default ClaimAssistant
