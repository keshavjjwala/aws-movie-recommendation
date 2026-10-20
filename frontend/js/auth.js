// Signing in. window.AUTH (config.js) picks the backend:
//   { mode: "cognito", region, clientId }  Amazon Cognito user pool (on AWS)
//   { mode: "local" }                       the API's built-in accounts (local development)
// The session (tokens + email) is kept in localStorage.

const SESSION_KEY = "movie-picks-session";
const config = window.AUTH || { mode: "local" };

function load() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY)) || null;
  } catch {
    return null;
  }
}

function save(session) {
  try {
    if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    else localStorage.removeItem(SESSION_KEY);
  } catch {
    // blocked storage: the session lasts for this visit only
  }
}

// Error with a short code the views can act on (e.g. "confirm" → show the code step).
class AuthError extends Error {
  constructor(message, code) {
    super(message);
    this.code = code;
  }
}

function claimsOf(jwt) {
  const part = jwt.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(part.padEnd(part.length + ((4 - (part.length % 4)) % 4), "=")));
}

// --- Amazon Cognito (called directly from the browser, no SDK) ---------------

const COGNITO_MESSAGES = {
  NotAuthorizedException: "Wrong email or password.",
  UsernameExistsException: "An account with this email already exists. Sign in instead.",
  CodeMismatchException: "That code isn't right. Check the email and try again.",
  ExpiredCodeException: "That code has expired. Send a new one.",
  LimitExceededException: "Too many attempts. Wait a few minutes and try again.",
  TooManyRequestsException: "Too many attempts. Wait a few minutes and try again.",
  InvalidParameterException: "Enter a valid email address.",
};

async function cognito(action, body) {
  let response;
  try {
    response = await fetch(config.endpoint || `https://cognito-idp.${config.region}.amazonaws.com/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": `AWSCognitoIdentityProviderService.${action}`,
      },
      body: JSON.stringify({ ClientId: config.clientId, ...body }),
    });
  } catch {
    throw new AuthError("Can't reach the sign-in service. Check your connection and try again.", "network");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const type = (data.__type || "").split("#").pop();
    if (type === "UserNotConfirmedException") {
      throw new AuthError("Confirm your email first. We've sent you a code.", "confirm");
    }
    if (type === "InvalidPasswordException") throw new AuthError("Use at least 8 characters for your password.");
    throw new AuthError(COGNITO_MESSAGES[type] || data.message || "Sign-in failed. Try again.");
  }
  return data;
}

function cognitoSession(result, refreshToken) {
  return {
    token: result.IdToken,
    refreshToken: refreshToken ?? result.RefreshToken,
    expiresAt: Date.now() + result.ExpiresIn * 1000,
    email: claimsOf(result.IdToken).email,
  };
}

const cognitoBackend = {
  needsConfirmation: true,
  async signUp(email, password) {
    await cognito("SignUp", { Username: email, Password: password, UserAttributes: [{ Name: "email", Value: email }] });
    return null; // a code was emailed; confirm() comes next
  },
  async confirm(email, code) {
    await cognito("ConfirmSignUp", { Username: email, ConfirmationCode: code });
  },
  async resend(email) {
    await cognito("ResendConfirmationCode", { Username: email });
  },
  async signIn(email, password) {
    const data = await cognito("InitiateAuth", {
      AuthFlow: "USER_PASSWORD_AUTH",
      AuthParameters: { USERNAME: email, PASSWORD: password },
    });
    return cognitoSession(data.AuthenticationResult);
  },
  async refresh(session) {
    const data = await cognito("InitiateAuth", {
      AuthFlow: "REFRESH_TOKEN_AUTH",
      AuthParameters: { REFRESH_TOKEN: session.refreshToken },
    });
    return cognitoSession(data.AuthenticationResult, session.refreshToken);
  },
};

// --- Local accounts (the API's stand-in for Cognito) --------------------------

async function local(path, email, password) {
  let response;
  try {
    response = await fetch((window.API_BASE || "") + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  } catch {
    throw new AuthError("Can't reach the server. Check that it's running and try again.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new AuthError(typeof data.detail === "string" ? data.detail : "Enter a valid email and password.");
  return { token: data.token, email: data.email, expiresAt: claimsOf(`x.${data.token.split(".")[0]}`).exp * 1000 };
}

const localBackend = {
  needsConfirmation: false,
  signUp: (email, password) => local("/api/auth/local/signup", email, password),
  signIn: (email, password) => local("/api/auth/local/login", email, password),
  refresh: async () => null, // local tokens last 7 days; then sign in again
};

// --- Public interface -------------------------------------------------------

const backend = config.mode === "cognito" ? cognitoBackend : localBackend;
const listeners = new Set();
let session = load();

function setSession(next) {
  session = next;
  save(next);
  listeners.forEach((fn) => fn());
}

export const auth = {
  needsConfirmation: backend.needsConfirmation,
  get signedIn() {
    return Boolean(session);
  },
  get email() {
    return session?.email ?? null;
  },

  async signUp(email, password) {
    const created = await backend.signUp(email.trim(), password);
    if (created) setSession(created);
  },
  confirm: (email, code) => backend.confirm(email.trim(), code.trim()),
  resend: (email) => backend.resend(email.trim()),
  async signIn(email, password) {
    setSession(await backend.signIn(email.trim(), password));
  },
  signOut() {
    setSession(null);
  },

  // A valid token for API calls, refreshed when it's about to expire; null if signed out.
  async token() {
    if (!session) return null;
    if (session.expiresAt - Date.now() < 60_000) {
      try {
        setSession(await backend.refresh(session));
      } catch (error) {
        if (error.code !== "network") setSession(null); // offline: keep the session, the API call will say so
      }
    }
    return session?.token ?? null;
  },

  subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
};
