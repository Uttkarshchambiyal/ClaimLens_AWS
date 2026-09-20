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
  help: `I can help you with:

• **Reviewing claims** – I'll highlight discrepancies and flag items needing attention
• **Understanding findings** – Ask me about any specific finding or check result
• **Document analysis** – I can explain extracted fields and confidence levels
• **Workflow guidance** – I'll walk you through the review process step by step

What would you like help with?`,

  status: `**Current Review Summary:**

📋 4 claims in queue
⚠️ 2 claims need review
✅ 1 claim fully reviewed
🔄 1 claim processing

The highest priority item is **CLM-20481** — invoice total reconciliation failed. Would you like me to walk you through that finding?`,

  finding: `**CLM-20481 – Invoice Total Reconciliation**

The itemized bill total (₹45,230.00) doesn't match the sum of line items (₹44,780.00). The ₹450 discrepancy is in the pharmacy section.

**Evidence:** CityCare_itemized_bill.pdf, page 3, rows 12-15

**Recommendation:** Check whether the pharmacy subtotal includes a rounding adjustment or missing line item. This is a deterministic finding — no AI interpretation involved.

Would you like me to check the discharge summary for related entries?`,

  default: `I understand your question. In the current mock mode, I'm demonstrating the AI assistant experience. In production, I would use Amazon Bedrock to analyze your specific claim documents, cross-reference findings, and provide source-linked explanations.

Is there something specific about the review workflow I can help you with?`,
}

function getMockResponse(input: string): string {
  const lower = input.toLowerCase()
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
      content: `Hi! I'm your ClaimLens AI assistant${appMode === 'mock' ? ' (mock mode)' : ''}. I can help you navigate findings, understand discrepancies, and guide your review workflow. What would you like to know?`,
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

      // Simulate AI thinking delay
      await new Promise((resolve) => setTimeout(resolve, 800 + Math.random() * 1200))

      const aiMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: getMockResponse(text),
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
        <div className="fixed bottom-6 right-6 z-[9999]">
          <ShinyButton
            onClick={() => setIsOpen(true)}
            compact
            aria-label="Open AI assistant"
          >
            <span className="flex items-center gap-2">
              <Sparkles size={18} />
              AI Assistant
            </span>
          </ShinyButton>
        </div>
      )}

      {/* Chat panel */}
      {isOpen && (
        <div
          className={cn(
            'fixed bottom-6 right-6 z-[9999]',
            'flex flex-col',
            'w-[380px] max-h-[600px] h-[600px]',
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
                  {appMode === 'mock'
                    ? 'Mock mode · No AWS calls'
                    : 'Powered by Amazon Bedrock'}
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
                  <div
                    className="[&_strong]:font-semibold [&_ul]:list-disc [&_ul]:pl-4 [&_ul]:my-1 [&_p]:my-1"
                    dangerouslySetInnerHTML={{
                      __html: message.content
                        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                        .replace(/\n/g, '<br/>')
                        .replace(/• /g, '&bull; '),
                    }}
                  />
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
