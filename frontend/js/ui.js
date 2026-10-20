// Small DOM helpers and shared components. All text goes in via textContent.

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  node.append(...children.flat(Infinity).filter((c) => c !== null && c !== undefined && c !== false));
  return node;
}

export const metaLine = (movie) =>
  [movie.year, movie.runtime && formatRuntime(movie.runtime), movie.genres?.slice(0, 3).join(", ")]
    .filter(Boolean)
    .join("  ·  ");

export function formatRuntime(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h ? `${h}h ${m}m` : `${m}m`;
}

// Generated poster for movies without TMDB artwork (or when images fail to load).
export function fallbackPoster(movie) {
  return el(
    "div",
    { class: "fallback", dataset: { genre: movie.genres?.[0] || "" }, "aria-hidden": "true" },
    el("span", { class: "fallback-title" }, movie.title),
    el("span", { class: "fallback-year" }, movie.year ?? "")
  );
}

export function poster(movie) {
  const frame = el("div", { class: "poster" });
  if (movie.poster) {
    const img = el("img", { src: movie.poster, alt: "", loading: "lazy", decoding: "async" });
    img.addEventListener("error", () => img.replaceWith(fallbackPoster(movie)), { once: true });
    frame.append(img);
  } else {
    frame.append(fallbackPoster(movie));
  }
  return frame;
}

// Optional label drawn on a card's poster (main.js shows the movie's list status).
let badgeFor = () => "";
export function setCardBadge(fn) {
  badgeFor = fn;
}

export function card(movie, { caption } = {}) {
  const frame = poster(movie);
  const badge = badgeFor(movie);
  if (badge) frame.append(el("span", { class: "card-badge" }, badge));
  return el(
    "a",
    { class: "card", href: `#/movie/${movie.id}` },
    frame,
    el("span", { class: "card-title" }, movie.title),
    el("span", { class: "card-meta" }, caption ?? movie.year ?? "")
  );
}

export function row(title, movies, { caption } = {}) {
  const track = el("div", { class: "row-track" }, movies.map((m) => card(m, { caption: caption?.(m) })));
  const scroll = (direction) => track.scrollBy({ left: direction * track.clientWidth * 0.85, behavior: "smooth" });
  return el(
    "section",
    { class: "row" },
    el(
      "div",
      { class: "row-head" },
      el("h2", {}, title),
      el(
        "div",
        { class: "row-arrows" },
        el("button", { type: "button", class: "arrow", "aria-label": `Scroll ${title} left`, onclick: () => scroll(-1) }, "‹"),
        el("button", { type: "button", class: "arrow", "aria-label": `Scroll ${title} right`, onclick: () => scroll(1) }, "›")
      )
    ),
    track
  );
}

export function grid(movies, { caption, extra } = {}) {
  return el(
    "div",
    { class: "grid" },
    movies.map((m) => {
      const c = card(m, { caption: caption?.(m) });
      return extra ? el("div", { class: "grid-item" }, c, extra(m)) : c;
    })
  );
}

// Five star buttons. onRate(n) is awaited; the stars show a hover preview.
export function stars(current, onRate, { label, large = false } = {}) {
  const group = el("div", { class: `stars${large ? " large" : ""}`, role: "group", "aria-label": label });
  const buttons = [1, 2, 3, 4, 5].map((n) =>
    el(
      "button",
      {
        type: "button",
        "aria-label": `${n} star${n > 1 ? "s" : ""}`,
        onclick: async () => {
          group.classList.add("busy");
          try {
            if ((await onRate(n)) !== false) paint(n);
          } finally {
            group.classList.remove("busy");
          }
        },
        onmouseenter: () => preview(n),
        onfocus: () => preview(n),
      },
      "★"
    )
  );
  let value = current;
  const paint = (n) => {
    value = n;
    buttons.forEach((b, i) => {
      b.classList.toggle("on", i < n);
      b.setAttribute("aria-pressed", String(i < n));
    });
  };
  const preview = (n) => buttons.forEach((b, i) => b.classList.toggle("preview", i < n));
  group.addEventListener("mouseleave", () => preview(0));
  group.addEventListener("focusout", () => preview(0));
  group.append(...buttons);
  paint(current);
  group.setValue = paint;
  return group;
}

let toastTimer;
export function toast(message) {
  const node = document.getElementById("toast");
  node.textContent = message;
  node.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.remove("show"), 3200);
}

export function skeletonRow(title) {
  return el(
    "section",
    { class: "row", "aria-busy": "true" },
    el("div", { class: "row-head" }, el("h2", {}, title)),
    el("div", { class: "row-track" }, Array.from({ length: 8 }, () => el("div", { class: "card skeleton" }, el("div", { class: "poster" }))))
  );
}

export function skeletonGrid(n = 12) {
  return el("div", { class: "grid", "aria-busy": "true" }, Array.from({ length: n }, () => el("div", { class: "card skeleton" }, el("div", { class: "poster" }))));
}

export function errorBox(message, retry) {
  return el(
    "div",
    { class: "error-box", role: "alert" },
    el("p", {}, message),
    retry && el("button", { type: "button", class: "btn", onclick: retry }, "Try again")
  );
}
