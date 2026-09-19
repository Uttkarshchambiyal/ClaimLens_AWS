import { Amplify } from 'aws-amplify'
import { fetchAuthSession, getCurrentUser, signOut as cognitoSignOut } from 'aws-amplify/auth'
import { appMode } from './appConfig'

export interface ClaimLensUser {
  id_token: string
  profile: Record<string, unknown>
}

let configured = false
let sessionRequest: Promise<ClaimLensUser | null> | undefined

export function configureAuth() {
  if (configured || appMode === 'mock') return
  const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID
  const userPoolClientId = import.meta.env.VITE_COGNITO_CLIENT_ID
  if (!userPoolId || !userPoolClientId) {
    throw new Error('Production Cognito configuration is incomplete. Mock fallback is disabled.')
  }
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId,
        userPoolClientId,
        loginWith: { email: true },
      },
    },
  })
  configured = true
}

export async function getOptionalUser(): Promise<ClaimLensUser | null> {
  if (appMode === 'mock') return null
  try {
    configureAuth()
    await getCurrentUser()
    const session = await fetchAuthSession()
    const idToken = session.tokens?.idToken
    if (!idToken) throw new Error('Your session is missing an ID token. Please log in again.')
    return { id_token: idToken.toString(), profile: idToken.payload as Record<string, unknown> }
  } catch {
    return null
  }
}

async function resolveUser(): Promise<ClaimLensUser | null> {
  const user = await getOptionalUser()
  if (!user && appMode !== 'mock') {
    const returnTo = `${window.location.pathname}${window.location.search}`
    window.location.assign(`/auth/login?returnTo=${encodeURIComponent(returnTo)}`)
  }
  return user
}

export function requireUser(): Promise<ClaimLensUser | null> {
  if (!sessionRequest) {
    sessionRequest = resolveUser().finally(() => {
      sessionRequest = undefined
    })
  }
  return sessionRequest
}

export async function signOut() {
  if (appMode === 'mock') return
  configureAuth()
  await cognitoSignOut()
  window.location.assign('/')
}
