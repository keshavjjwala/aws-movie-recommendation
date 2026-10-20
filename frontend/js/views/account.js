import { api } from "../api.js";
import { auth } from "../auth.js";
import { go } from "../router.js";
import { el, poster } from "../ui.js";

// #/signin and #/signup. On Cognito, sign-up has a second step: the code we email.
export function renderAccount(view, mode, next = "#/") {
  const signingUp = mode === "signup";
  document.title = `${signingUp ? "Create account" : "Sign in"} · Movie Picks`;

  const wall = el("div", { class: "auth-wall", "aria-hidden": "true" });
  const panel = el("div", { class: "auth-panel" });
  view.replaceChildren(el("section", { class: "auth-page" }, wall, panel));
  fillWall(wall);

  const error = el("p", { class: "form-error", role: "alert" });
  const showError = (message) => {
    error.textContent = message || "";
  };

  passwordStep();

  function passwordStep(prefill = "") {
    const email = field("Email", { type: "email", name: "email", autocomplete: "email", required: true, value: prefill });
    const password = field("Password", {
      type: "password",
      name: "password",
      autocomplete: signingUp ? "new-password" : "current-password",
      required: true,
      minlength: signingUp ? 8 : null,
    });
    const submit = el("button", { type: "submit", class: "btn primary wide" }, signingUp ? "Create account" : "Sign in");
    const form = el(
      "form",
      { class: "auth-form", novalidate: true },
      el("h1", {}, signingUp ? "Create your account" : "Welcome back"),
      el("p", { class: "lede" }, signingUp
        ? "Keep a list of what you've watched and want to watch, and get picks that follow your taste."
        : "Sign in to see your list and your picks."),
      email.label,
      password.label,
      signingUp && el("p", { class: "hint" }, "At least 8 characters."),
      error,
      submit,
      el("p", { class: "switch" },
        signingUp ? "Already have an account? " : "New to Movie Picks? ",
        el("a", { href: signingUp ? "#/signin" : "#/signup" }, signingUp ? "Sign in" : "Create an account"))
    );
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      showError("");
      if (!email.input.value.trim() || !password.input.value) return showError("Enter your email and password.");
      if (signingUp && password.input.value.length < 8) return showError("Use at least 8 characters for your password.");
      busy(submit, signingUp ? "Creating account…" : "Signing in…");
      try {
        if (signingUp) {
          await auth.signUp(email.input.value, password.input.value);
          if (auth.needsConfirmation) return codeStep(email.input.value, password.input.value);
        } else {
          await auth.signIn(email.input.value, password.input.value);
        }
        go(signingUp ? "#/welcome" : next);
      } catch (e) {
        if (e.code === "confirm") {
          await auth.resend(email.input.value).catch(() => {});
          return codeStep(email.input.value, password.input.value);
        }
        showError(e.message);
        idle(submit);
      }
    });
    panel.replaceChildren(form);
    (prefill ? password : email).input.focus();
  }

  function codeStep(email, password) {
    showError("");
    const code = field("Verification code", {
      name: "code", inputmode: "numeric", autocomplete: "one-time-code", maxlength: 6, required: true,
    });
    const submit = el("button", { type: "submit", class: "btn primary wide" }, "Confirm email");
    const resend = el("button", { type: "button", class: "link-btn" }, "Send a new code");
    const form = el(
      "form",
      { class: "auth-form", novalidate: true },
      el("h1", {}, "Check your email"),
      el("p", { class: "lede" }, `We sent a 6-digit code to ${email}. Enter it to finish creating your account.`),
      code.label,
      error,
      submit,
      el("p", { class: "switch" }, "No email after a minute? ", resend)
    );
    resend.addEventListener("click", async () => {
      try {
        await auth.resend(email);
        showError("");
        resend.textContent = "New code sent";
      } catch (e) {
        showError(e.message);
      }
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!code.input.value.trim()) return showError("Enter the code from the email.");
      busy(submit, "Confirming…");
      try {
        await auth.confirm(email, code.input.value);
        await auth.signIn(email, password);
        go("#/welcome");
      } catch (e) {
        showError(e.message);
        idle(submit);
      }
    });
    panel.replaceChildren(form);
    code.input.focus();
  }
}

function field(text, attrs) {
  const input = el("input", attrs);
  return { input, label: el("label", { class: "field" }, el("span", {}, text), input) };
}

function busy(button, text) {
  button.dataset.label = button.textContent;
  button.textContent = text;
  button.disabled = true;
}

function idle(button) {
  button.textContent = button.dataset.label;
  button.disabled = false;
}

// A wall of popular posters behind the form; purely decorative.
async function fillWall(wall) {
  try {
    const movies = await api.popular(30);
    wall.replaceChildren(...movies.map((m) => poster(m)));
  } catch {
    // the page works without it
  }
}
