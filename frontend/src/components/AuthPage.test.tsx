import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthPage } from './AuthPage'

const auth = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  signIn: vi.fn(),
  signUp: vi.fn(),
  confirmSignUp: vi.fn(),
  autoSignIn: vi.fn(),
}))

vi.mock('aws-amplify/auth', () => auth)

beforeEach(() => {
  auth.getCurrentUser.mockRejectedValue(new Error('No session'))
  auth.signUp.mockResolvedValue({
    isSignUpComplete: false,
    nextStep: { signUpStep: 'CONFIRM_SIGN_UP' },
  })
})

describe('ClaimLens authentication pages', () => {
  it('shows a clear login form and account link', () => {
    render(<AuthPage mode="login" />)
    expect(screen.getByRole('heading', { name: 'Log in' })).toBeVisible()
    expect(screen.getByLabelText('Email')).toHaveAttribute('autocomplete', 'email')
    expect(screen.getByLabelText('Password')).toHaveAttribute('autocomplete', 'current-password')
    expect(screen.getByRole('link', { name: 'Create account' })).toHaveAttribute(
      'href',
      '/auth/signup',
    )
  })

  it('moves a valid signup into email confirmation', async () => {
    const user = userEvent.setup()
    render(<AuthPage mode="signup" />)
    await user.type(screen.getByLabelText('Full name'), 'Demo Reviewer')
    await user.type(screen.getByLabelText('Email'), 'reviewer@example.com')
    await user.type(screen.getByLabelText('Password'), 'StrongPassword#2026')
    await user.click(screen.getByRole('button', { name: /Create account/ }))
    expect(auth.signUp).toHaveBeenCalledWith(
      expect.objectContaining({ username: 'reviewer@example.com' }),
    )
    expect(await screen.findByRole('heading', { name: 'Check your email' })).toBeVisible()
    expect(screen.getByLabelText('Verification code')).toHaveAttribute(
      'autocomplete',
      'one-time-code',
    )
  })
})
