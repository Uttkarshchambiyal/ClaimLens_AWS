import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Bot,
  X,
  Send,
  Loader2,
  Sparkles,
  FileText,
  AlertTriangle,
  CheckCircle2,
  MessageSquare,
  Minimize2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { appMode } from '@/appConfig'
import { demoAnalysis } from '@/mockData'
import { ShinyButton } from './shiny-button'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

interface QuickAction {
  label: string
  prompt: string
  icon: React.ReactNode
}

/* ------------------------------------------------------------------ */
/*  Simulated AI responses (mock mode)                                 */
/* ------------------------------------------------------------------ */

const MOCK_RESPONSES: Record<string, string> = {
  help: `I can help you work through the current packet without making a coverage or fraud decision.

Ask for the review summary, invoice total, timeline, or missing evidence. I will give you the source document, page, and a reviewer next step.`,

  status: `Current review summary for CLM-20481:

• 2 high-priority findings need attention.
• 3 checks need reviewer follow-up, including one missing-evidence item.
• 1 identity check passed.

Start with the invoice-total and procedure-date findings. The packet is completed with warnings, so review remains required.`,

  finding: `CLM-20481 – Invoice Total Reconciliation

The stated invoice total is ₹248,500.00 and the extracted line items sum to ₹241,500.00. The difference is ₹7,000.00.

Evidence: CityCare_itemized_bill.pdf, pages 2–3.

Recommendation: Check for an omitted line item, adjustment, or extraction error. This is a deterministic finding — no AI interpretation involved.

Would you like me to check the discharge summary for related entries?`,

  default: `I can answer from the current synthetic packet when your question relates to a finding, document, date, amount, or missing evidence. Try “Explain the invoice total” or “What evidence is missing?”

This demo assistant is informational only: it does not approve, reject, or adjudicate claims.`,
}

function getMockResponse(input: string): string {
  const lower = input.toLowerCase()
  const total = demoAnalysis.findings.find(
    (finding) => finding.checkId === 'bill.total_reconciliation',
  )
  const timeline = demoAnalysis.findings.find((finding) => finding.checkId === 'packet.timeline')
  const missing = demoAnalysis.findings.find(
    (finding) => finding.checkId === 'packet.supporting_evidence',
  )
  const cite = (finding: typeof total) =>
    finding?.evidence.map((item) => `${item.documentName}, page ${item.page}`).join('; ')
  if (
    lower.includes('invoice') ||
    lower.includes('total') ||
    lower.includes('amount') ||
    lower.includes('reconcil') ||
    lower.includes('discrepancy')
  )
    return `${total?.title}\n\n${total?.summary}\n\nEvidence: ${cite(total)}.\n\nNext step: open both citations and check for an omitted line item, adjustment, or extraction error. This is a reconciliation check, not a decision about claim validity.`
  if (lower.includes('date') || lower.includes('timeline') || lower.includes('procedure'))
    return `${timeline?.title}\n\n${timeline?.summary}\n\nEvidence: ${cite(timeline)}.\n\nNext step: verify the source dates and determine whether a documented exception explains the sequence before recording a disposition.`
  if (lower.includes('missing') || lower.includes('evidence') || lower.includes('implant'))
    return `${missing?.title}\n\n${missing?.summary}\n\nEvidence: ${cite(missing)}.\n\nNext step: ${missing?.requestedEvidence} Do not treat the missing document as proof that the service did not occur.`
  if (lower.includes('finding') || lower.includes('priority'))
    return `Top findings for ${demoAnalysis.claimId}:\n\n• ${total?.title}: ${total?.summary}\n• ${timeline?.title}: ${timeline?.summary}\n\nReview the cited source pages before acknowledging or resolving either item.`
  if (lower.includes('help') || lower.includes('what can')) return MOCK_RESPONSES.help
  if (lower.includes('status') || lower.includes('summary') || lower.includes('queue'))
    return MOCK_RESPONSES.status
  if (
    lower.includes('finding') ||
    lower.includes('clm-') ||
    lower.includes('reconcil') ||
    lower.includes('discrepancy')
  )
    return MOCK_RESPONSES.finding
  return MOCK_RESPONSES.default
}

function MessageContent({ content }: { content: string }) {
  return (
    <div className="space-y-2 whitespace-pre-line break-words">
      {content.split('\n\n').map((paragraph, index) => (
        <p key={index}>{paragraph}</p>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Quick Actions                                                      */
/* ------------------------------------------------------------------ */

const quickActions: QuickAction[] = [
  {
    label: 'Review summary',
    prompt: 'Show me a summary of the current review queue status',
    icon: <FileText size={14} />,
  },
  {
    label: 'Top findings',
    prompt: 'What are the highest priority findings I should review?',
    icon: <AlertTriangle size={14} />,
  },
  {
    label: 'How to review',
    prompt: 'Help me understand the review workflow',
    icon: <CheckCircle2 size={14} />,
  },
]

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function AIAgentWidget() {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        appMode === 'mock'
          ? 'Hi! I’m your ClaimLens demo assistant. I can explain the current packet’s findings and point you to evidence. What would you like to review?'
          : 'The live assistant is not connected in this build. I cannot safely answer from claim documents until a source-grounded endpoint is enabled.',
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [isOpen])

  useEffect(() => {
    const openAssistant = () => setIsOpen(true)
    window.addEventListener('claimlens:open-assistant', openAssistant)
    return () => window.removeEventListener('claimlens:open-assistant', openAssistant)
  }, [])

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isTyping) return

      const userMessage: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content: text.trim(),
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, userMessage])
      setInput('')
      setIsTyping(true)

      // Keep the demo responsive without pretending that an external model was called.
      await new Promise((resolve) => setTimeout(resolve, 350))

      const aiMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content:
          appMode === 'mock'
            ? getMockResponse(text)
            : 'The live assistant is not connected in this build, so I cannot safely answer from claim documents. Use the cited findings and source viewer, or connect a source-grounded assistant endpoint before enabling this chat.',
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, aiMessage])
      setIsTyping(false)
    },
    [isTyping],
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void sendMessage(input)
  }

  return (
    <>
      {/* Floating trigger button */}
      {!isOpen && (
        <div className="fixed bottom-6 right-6 z-50">
          <ShinyButton
            className="flex items-center gap-2 shadow-xl shadow-black/20"
            onClick={() => setIsOpen(true)}
            aria-label="Open ClaimLens AI Assistant"
          >
            <Sparkles size={20} />
            <span>Ask ClaimLens</span>
          </ShinyButton>
        </div>
      )}

      {/* Chat panel */}
      {isOpen && (
        <div
          className={cn(
            'fixed bottom-6 right-6 z-[9999]',
            'flex flex-col',
            'w-[calc(100vw-2rem)] sm:w-[380px] max-h-[min(600px,calc(100dvh-2rem))] h-[min(600px,calc(100dvh-2rem))]',
            'rounded-2xl shadow-2xl',
            'overflow-hidden',
          )}
          style={{
            border: '1px solid var(--border)',
            background: 'var(--surface, #ffffff)',
          }}
          role="dialog"
          aria-label="AI assistant chat"
        >
          {/* Header */}
          <div
            className="flex items-center justify-between px-4 py-3"
            style={{
              background: 'var(--primary, #122023)',
              color: 'var(--primary-foreground, #e1fcad)',
              borderBottom: '1px solid rgba(255,255,255,0.1)',
            }}
          >
            <div className="flex items-center gap-2.5">
              <div
                className="flex h-8 w-8 items-center justify-center rounded-full"
                style={{ background: 'var(--accent-soft, rgba(223,247,173,0.4))' }}
              >
                <Bot size={18} style={{ color: 'var(--accent, #607b35)' }} />
              </div>
              <div>
                <h3 className="text-sm font-semibold">ClaimLens AI</h3>
                <p className="text-[10px]" style={{ opacity: 0.6 }}>
                  {appMode === 'mock' ? 'Mock mode · No AWS calls' : 'Live assistant unavailable'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setIsOpen(false)}
                className="rounded-lg p-1.5 transition-colors"
                style={{ color: 'rgba(255,255,255,0.6)' }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#fff')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.6)')}
                aria-label="Minimize AI assistant"
              >
                <Minimize2 size={16} />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="rounded-lg p-1.5 transition-colors"
                style={{ color: 'rgba(255,255,255,0.6)' }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#fff')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.6)')}
                aria-label="Close AI assistant"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div
            className="flex-1 overflow-y-auto px-4 py-3 space-y-3"
            style={{ background: 'var(--background, #f3f5ee)' }}
          >
            {messages.map((message) => (
              <div
                key={message.id}
                className={cn('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}
              >
                <div
                  className="max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed"
                  style={
                    message.role === 'user'
                      ? {
                          background: 'var(--primary, #122023)',
                          color: 'var(--primary-foreground, #e1fcad)',
                          borderBottomRightRadius: '0.375rem',
                        }
                      : {
                          background: 'var(--surface-raised, #ffffff)',
                          color: 'var(--foreground, #122023)',
                          border: '1px solid var(--border, #1220231a)',
                          borderBottomLeftRadius: '0.375rem',
                        }
                  }
                >
                  <MessageContent content={message.content} />
                  <p
                    className="text-[10px] mt-1"
                    style={{
                      color:
                        message.role === 'user'
                          ? 'rgba(255,255,255,0.4)'
                          : 'var(--text-muted, #687270)',
                    }}
                  >
                    {message.timestamp.toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </p>
                </div>
              </div>
            ))}

            {isTyping && (
              <div className="flex justify-start">
                <div
                  className="flex items-center gap-2 rounded-2xl px-4 py-3"
                  style={{
                    background: 'var(--surface-raised, #ffffff)',
                    border: '1px solid var(--border, #1220231a)',
                    borderBottomLeftRadius: '0.375rem',
                  }}
                >
                  <Loader2
                    size={14}
                    className="animate-spin"
                    style={{ color: 'var(--accent, #607b35)' }}
                  />
                  <span className="text-sm" style={{ color: 'var(--text-muted, #687270)' }}>
                    Thinking…
                  </span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Quick actions (only show when few messages) */}
          {messages.length <= 1 && (
            <div className="px-4 pb-2" style={{ background: 'var(--background, #f3f5ee)' }}>
              <div className="flex flex-wrap gap-1.5">
                {quickActions.map((action) => (
                  <button
                    key={action.label}
                    onClick={() => void sendMessage(action.prompt)}
                    className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs transition-colors"
                    style={{
                      border: '1px solid var(--border, #1220231a)',
                      color: 'var(--text-secondary, #3e4a49)',
                      background: 'var(--surface, #ffffff)',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'var(--surface-hover, #f0f3ea)'
                      e.currentTarget.style.borderColor = 'var(--accent-border, #85a64b70)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'var(--surface, #ffffff)'
                      e.currentTarget.style.borderColor = 'var(--border, #1220231a)'
                    }}
                  >
                    {action.icon}
                    {action.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input area */}
          <form
            onSubmit={handleSubmit}
            className="flex items-center gap-2 px-3 py-2.5"
            style={{
              borderTop: '1px solid var(--border, #1220231a)',
              background: 'var(--surface, #ffffff)',
            }}
          >
            <MessageSquare
              size={16}
              className="shrink-0"
              style={{ color: 'var(--text-muted, #687270)' }}
            />
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about a claim or finding…"
              className="flex-1 bg-transparent text-sm outline-none"
              style={{
                color: 'var(--foreground, #122023)',
              }}
              disabled={isTyping}
            />
            <button
              type="submit"
              disabled={!input.trim() || isTyping}
              className="rounded-lg p-2 transition-colors"
              style={
                input.trim() && !isTyping
                  ? {
                      background: 'var(--primary, #122023)',
                      color: 'var(--primary-foreground, #e1fcad)',
                    }
                  : {
                      color: 'var(--muted-foreground, #687270)',
                      cursor: 'not-allowed',
                      opacity: 0.4,
                    }
              }
              aria-label="Send message"
            >
              <Send size={16} />
            </button>
          </form>
        </div>
      )}
    </>
  )
}

export default AIAgentWidget
