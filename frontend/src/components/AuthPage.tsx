import { FormEvent, useEffect, useState } from 'react'
import { autoSignIn, confirmSignUp, getCurrentUser, signIn, signUp } from 'aws-amplify/auth'
import { ArrowLeft, ArrowRight, Check, LockKeyhole, Mail, ShieldCheck } from 'lucide-react'
import { configureAuth } from '../auth'
import { ThemeToggle } from './ui/theme-toggle'
import '../auth.css'

type Mode = 'login' | 'signup'

const messageFor = (error: unknown) => {
  if (!(error instanceof Error)) return 'Something went wrong. Please try again.'
  if (error.name === 'UserNotConfirmedException') return 'Confirm your email before logging in.'
  if (error.name === 'NotAuthorizedException') return 'The email or password is incorrect.'
  if (error.name === 'UsernameExistsException') return 'An account with this email already exists.'
  return error.message
}

export function AuthPage({ mode }: { mode: Mode }) {
  const [step, setStep] = useState<'details' | 'confirm'>('details')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const destination = () => {
    const returnTo = new URLSearchParams(window.location.search).get('returnTo')
    return returnTo?.startsWith('/') && !returnTo.startsWith('//') ? returnTo : '/'
  }

  useEffect(() => {
    configureAuth()
    void getCurrentUser()
      .then(() => window.location.replace(destination()))
      .catch(() => undefined)
  }, [])

  const finish = () => {
    window.dispatchEvent(new Event('claimlens:auth-changed'))
    window.location.replace(destination())
  }

  const submitDetails = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (mode === 'login') {
        const result = await signIn({ username: email.trim(), password })
        if (result.isSignedIn) finish()
        else setError('This account requires an additional sign-in step that is not configured.')
      } else {
        const result = await signUp({
          username: email.trim(),
          password,
          options: {
            userAttributes: { email: email.trim(), name: name.trim() },
            autoSignIn: true,
          },
        })
        if (result.isSignUpComplete) {
          try {
            const signedIn = await autoSignIn()
            if (signedIn.isSignedIn) finish()
          } catch {
            window.location.assign('/auth/login')
          }
        } else {
          setStep('confirm')
        }
      }
    } catch (caught) {
      setError(messageFor(caught))
    } finally {
      setBusy(false)
    }
  }

  const submitConfirmation = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await confirmSignUp({ username: email.trim(), confirmationCode: code.trim() })
      if (result.isSignUpComplete) {
        try {
          const signedIn = await autoSignIn()
          if (signedIn.isSignedIn) finish()
          else window.location.assign('/auth/login')
        } catch {
          window.location.assign('/auth/login')
        }
      }
    } catch (caught) {
      setError(messageFor(caught))
    } finally {
      setBusy(false)
    }
  }

  const signup = mode === 'signup'
  return (
    <main className="auth-shell">
      <section className="auth-story" aria-label="ClaimLens account benefits">
        <a href="/" className="auth-brand" aria-label="ClaimLens home">
          <span>
            <ShieldCheck size={20} />
          </span>{' '}
          ClaimLens
        </a>
        <div>
          <span className="auth-kicker">
            <LockKeyhole size={15} /> Private by design
          </span>
          <h1>
            {signup ? 'Your review workspace starts here.' : 'Welcome back to clearer reviews.'}
          </h1>
          <p>
            Each account receives an isolated workspace for claim packets, findings, and review
            activity.
          </p>
          <ul>
            <li>
              <Check size={16} /> Credentials protected by Amazon Cognito
            </li>
            <li>
              <Check size={16} /> Source-linked findings and audit history
            </li>
            <li>
              <Check size={16} /> Human decisions remain in your control
            </li>
          </ul>
        </div>
        <small>Synthetic hackathon prototype · Do not upload real patient data</small>
      </section>

      <section className="auth-form-side">
        <div className="auth-topbar">
          <a href="/">
            <ArrowLeft size={16} /> Back home
          </a>
          <ThemeToggle />
        </div>
        <div className="auth-card">
          <span className="auth-card-icon">
            <ShieldCheck size={22} />
          </span>
          <h2>
            {step === 'confirm' ? 'Check your email' : signup ? 'Create your account' : 'Log in'}
          </h2>
          <p>
            {step === 'confirm'
              ? `Enter the verification code sent to ${email}.`
              : signup
                ? 'Use your email to create a private ClaimLens workspace.'
                : 'Enter your account details to open your workspace.'}
          </p>

          {step === 'confirm' ? (
            <form onSubmit={submitConfirmation}>
              <label htmlFor="confirmation-code">Verification code</label>
              <input
                id="confirmation-code"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                inputMode="numeric"
                autoComplete="one-time-code"
                required
              />
              {error && (
                <div className="auth-error" role="alert">
                  {error}
                </div>
              )}
              <button type="submit" disabled={busy}>
                {busy ? 'Confirming…' : 'Confirm email'} <ArrowRight size={17} />
              </button>
              <button type="button" className="auth-text-button" onClick={() => setStep('details')}>
                Change account details
              </button>
            </form>
          ) : (
            <form onSubmit={submitDetails}>
              {signup && (
                <>
                  <label htmlFor="full-name">Full name</label>
                  <input
                    id="full-name"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    autoComplete="name"
                    required
                  />
                </>
              )}
              <label htmlFor="email">Email</label>
              <div className="auth-input-wrap">
                <Mail size={17} />
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  required
                />
              </div>
              <label htmlFor="password">Password</label>
              <div className="auth-input-wrap">
                <LockKeyhole size={17} />
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete={signup ? 'new-password' : 'current-password'}
                  minLength={12}
                  required
                />
              </div>
              {signup && (
                <small className="auth-password-note">
                  At least 12 characters with uppercase, lowercase, number, and symbol.
                </small>
              )}
              {error && (
                <div className="auth-error" role="alert">
                  {error}
                </div>
              )}
              <button type="submit" disabled={busy}>
                {busy ? 'Please wait…' : signup ? 'Create account' : 'Log in'}{' '}
                <ArrowRight size={17} />
              </button>
            </form>
          )}

          {step === 'details' && (
            <p className="auth-switch">
              {signup ? 'Already have an account?' : 'New to ClaimLens?'}{' '}
              <a href={signup ? '/auth/login' : '/auth/signup'}>
                {signup ? 'Log in' : 'Create account'}
              </a>
            </p>
          )}
          <div className="auth-security">
            <LockKeyhole size={14} /> Passwords are handled directly by Amazon Cognito and are never
            stored by ClaimLens.
          </div>
        </div>
      </section>
    </main>
  )
}
