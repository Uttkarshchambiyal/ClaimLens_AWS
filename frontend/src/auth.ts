import { OidcClient, UserManager, WebStorageStateStore, type User } from 'oidc-client-ts'
import { appMode } from './api'

let manager: UserManager | undefined
let sessionRequest: Promise<User | null> | undefined

function getManager() {
  if (manager) return manager
  const authority = import.meta.env.VITE_COGNITO_AUTHORITY
  const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID
  const redirectUri = import.meta.env.VITE_COGNITO_REDIRECT_URI
  if (!authority || !clientId || !redirectUri)
    throw new Error(
      'Production Cognito OIDC configuration is incomplete. Mock fallback is disabled.',
    )
  const sessionStore = new WebStorageStateStore({ store: window.sessionStorage })
  manager = new UserManager({
    authority,
    client_id: clientId,
    redirect_uri: redirectUri,
    post_logout_redirect_uri: import.meta.env.VITE_COGNITO_LOGOUT_URI,
    response_type: 'code',
    scope: 'openid email profile',
    userStore: sessionStore,
    stateStore: sessionStore,
    automaticSilentRenew: true,
  })
  return manager
}

async function resolveUser(): Promise<User | null> {
  if (appMode === 'mock') return null
  const oidc = getManager()
  if (window.location.pathname === '/auth/signup') {
    const request = await new OidcClient(oidc.settings).createSigninRequest({})
    const signupUrl = new URL(request.url)
    signupUrl.pathname = '/signup'
    window.location.assign(signupUrl.toString())
    return null
  }
  if (window.location.pathname === '/auth/login') {
    await oidc.signinRedirect()
    return null
  }
  if (window.location.pathname === '/auth/callback' && window.location.search) {
    const user = await oidc.signinRedirectCallback()
    window.history.replaceState({}, document.title, '/review')
    return user
  }
  let user = await oidc.getUser()
  if (user?.expired) {
    try {
      user = await oidc.signinSilent()
    } catch {
      user = null
    }
  }
  if (!user || user.expired) {
    await oidc.signinRedirect()
    return null
  }
  return user
}

export function requireUser(): Promise<User | null> {
  // React StrictMode must not exchange the same authorization code twice.
  if (!sessionRequest)
    sessionRequest = resolveUser().finally(() => {
      sessionRequest = undefined
    })
  return sessionRequest
}

export async function signOut() {
  if (appMode === 'mock') return
  const domain = import.meta.env.VITE_COGNITO_DOMAIN
  const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID
  const logoutUri = import.meta.env.VITE_COGNITO_LOGOUT_URI
  if (!domain || !clientId || !logoutUri)
    throw new Error('Cognito sign-out configuration is incomplete.')
  await getManager().removeUser()
  const logout = new URL('/logout', domain)
  logout.searchParams.set('client_id', clientId)
  logout.searchParams.set('logout_uri', logoutUri)
  window.location.assign(logout.toString())
}
