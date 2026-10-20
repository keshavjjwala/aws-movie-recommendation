// Hash routes: #/, #/welcome, #/movie/12, #/search?q=alien, #/list?status=watching, #/signin, #/signup

export function currentRoute() {
  const raw = location.hash.replace(/^#/, "") || "/";
  const [path, query = ""] = raw.split("?");
  const params = new URLSearchParams(query);
  const movie = path.match(/^\/movie\/(\d+)$/);
  if (movie) return { name: "movie", id: Number(movie[1]), params };
  const names = {
    "/": "home", "/welcome": "welcome", "/search": "search", "/list": "list", "/ratings": "ratings",
    "/signin": "signin", "/signup": "signup",
  };
  return { name: names[path] || "notfound", params };
}

export function go(hash, { replace = false } = {}) {
  if (replace) {
    history.replaceState(null, "", hash);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  } else {
    location.hash = hash;
  }
}
