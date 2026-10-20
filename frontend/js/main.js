import { auth } from "./auth.js";
import { library, statusLabel } from "./library.js";
import { currentRoute, go } from "./router.js";
import { el, errorBox, setCardBadge, toast } from "./ui.js";
import { renderAccount } from "./views/account.js";
import { renderHome } from "./views/home.js";
import { renderList } from "./views/list.js";
import { renderMovie } from "./views/movie.js";
import { renderSearch } from "./views/search.js";
import { renderWelcome } from "./views/welcome.js";

const main = document.getElementById("view");
const searchInput = document.getElementById("search-input");
const nav = document.getElementById("account-nav");
const PERSONAL = new Set(["welcome", "list"]);

setCardBadge((movie) => statusLabel(library.statusOf(movie.id)));

function drawNav() {
  if (!auth.signedIn) {
    nav.replaceChildren(el("a", { class: "btn primary small", href: "#/signin" }, "Sign in"));
    return;
  }
  const count = library.entries.size;
  const menu = el(
    "details",
    { class: "account" },
    el("summary", { "aria-label": `Account: ${auth.email}` }, (auth.email || "?")[0].toUpperCase()),
    el("div", { class: "account-menu" },
      el("p", { class: "account-email" }, auth.email),
      el("button", { type: "button", class: "btn ghost small", onclick: signOut }, "Sign out"))
  );
  nav.replaceChildren(
    el("a", { class: "nav-link", href: "#/list" }, "My list", count ? el("span", { class: "badge" }, count) : ""),
    menu
  );
}
function signOut() {
  auth.signOut();
  toast("Signed out.");
}
library.subscribe(drawNav);
auth.subscribe(() => {
  library.clear();
  drawNav();
  // Signed out (by the user or an expired session): leave personal pages for home.
  if (!auth.signedIn) PERSONAL.has(currentRoute().name) ? go("#/", { replace: true }) : render();
});
document.addEventListener("click", (e) => {
  const open = nav.querySelector("details[open]");
  if (open && !open.contains(e.target)) open.removeAttribute("open");
});

async function render() {
  const route = currentRoute();
  // Each render draws into a fresh container, so a slow response for a page
  // the visitor already left lands in a detached node instead of the screen.
  const view = document.createElement("div");
  main.replaceChildren(view);
  nav.querySelector("details[open]")?.removeAttribute("open");

  if (route.name === "ratings") return go("#/list", { replace: true });
  if (PERSONAL.has(route.name) && !auth.signedIn) {
    return go(`#/signin?next=${encodeURIComponent(location.hash)}`, { replace: true });
  }
  if ((route.name === "signin" || route.name === "signup") && auth.signedIn) return go("#/", { replace: true });

  if (!library.loaded) {
    try {
      await library.load();
    } catch (error) {
      if (error.status === 401) return; // signed out by the API; the auth listener re-renders
      view.replaceChildren(errorBox(`Couldn't load your list. ${error.message}`, render));
      return;
    }
  }
  if (route.name === "home" && library.needsWelcome()) return go("#/welcome", { replace: true });

  document.body.classList.remove("bare");
  document.title = "Movie Picks";
  if (route.name !== "search") searchInput.value = "";
  if (route.name !== "search") window.scrollTo(0, 0);

  switch (route.name) {
    case "welcome": return renderWelcome(view);
    case "movie": return renderMovie(view, route.id);
    case "search": return renderSearch(view, route.params.get("q")?.trim() || "");
    case "list": return renderList(view, route.params.get("status"));
    case "signin": return renderAccount(view, "signin", safeNext(route.params.get("next")));
    case "signup": return renderAccount(view, "signup");
    case "home": return renderHome(view);
    default: return go("#/", { replace: true });
  }
}

// Only follow "next" to one of our own hash routes.
const safeNext = (next) => (next && /^#\/[\w/?=&%-]*$/.test(next) ? next : "#/");

let searchTimer;
searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    const q = searchInput.value.trim();
    const hash = q ? `#/search?q=${encodeURIComponent(q)}` : "#/";
    // While already on search, replace the history entry instead of adding one per keystroke.
    go(hash, { replace: currentRoute().name === "search" });
  }, 250);
});
document.getElementById("search-form").addEventListener("submit", (e) => e.preventDefault());

window.addEventListener("hashchange", render);
drawNav();
render();
