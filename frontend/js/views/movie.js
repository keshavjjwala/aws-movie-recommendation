import { api } from "../api.js";
import { rateMovie, removeFromList, removeRating, setStatus } from "../actions.js";
import { auth } from "../auth.js";
import { library, STATUSES } from "../library.js";
import { el, errorBox, metaLine, poster, row, skeletonRow, stars } from "../ui.js";

export async function renderMovie(view, id) {
  view.replaceChildren(el("div", { class: "movie-banner skeleton" }), skeletonRow("More like this"));

  let movie, similar;
  try {
    [movie, similar] = await Promise.all([api.movie(id), api.similar(id, 20)]);
  } catch (error) {
    const message = error.message.startsWith("Unknown movie") ? "We couldn't find that movie." : `Couldn't load this movie. ${error.message}`;
    view.replaceChildren(errorBox(message, () => renderMovie(view, id)));
    return;
  }
  document.title = `${movie.title} · Movie Picks`;

  const panel = listPanel(movie);

  const facts = [
    movie.director && ["Directed by", movie.director],
    movie.cast.length && ["Starring", movie.cast.join(", ")],
    movie.avg && ["MovieLens users", `${movie.avg} out of 5 from ${movie.count.toLocaleString()} ratings`],
  ].filter(Boolean);

  view.replaceChildren(
    el(
      "article",
      { class: "movie" },
      el(
        "div",
        { class: "movie-banner", dataset: { genre: movie.genres?.[0] || "" } },
        movie.backdrop && el("img", { src: movie.backdrop, alt: "", onerror: (e) => e.target.remove() })
      ),
      el(
        "div",
        { class: "movie-main" },
        el("div", { class: "movie-poster" }, poster(movie)),
        el(
          "div",
          { class: "movie-info" },
          el("h1", {}, movie.title),
          el("p", { class: "movie-meta" }, metaLine(movie)),
          movie.tagline && el("p", { class: "movie-tagline" }, movie.tagline),
          el("p", { class: "movie-overview" }, movie.overview || "No plot summary available for this movie yet."),
          facts.length && el("dl", { class: "facts" }, facts.map(([k, v]) => [el("dt", {}, k), el("dd", {}, v)])),
          panel
        )
      )
    ),
    similar.length ? row("More like this", similar) : ""
  );
}

// "Your list" box: status buttons, rating stars, remove. Signed out: a sign-in prompt.
function listPanel(movie) {
  const box = el("section", { class: "your-list", "aria-labelledby": "your-list-title" });
  if (!auth.signedIn) {
    box.append(
      el("h2", { id: "your-list-title" }, "Your list"),
      el("p", { class: "your-label" }, "Sign in to rate this movie and keep track of what you watch."),
      el("a", { class: "btn primary small", href: `#/signin?next=${encodeURIComponent(`#/movie/${movie.id}`)}` }, "Sign in")
    );
    return box;
  }

  const statusButtons = STATUSES.map((s) =>
    el("button", {
      type: "button",
      class: "seg",
      onclick: async () => {
        if (library.statusOf(movie.id) !== s.id && (await setStatus(movie, s.id))) refresh();
      },
    }, s.label)
  );
  const removeListed = el("button", {
    type: "button",
    class: "link-btn",
    onclick: async () => {
      if (await removeFromList(movie)) refresh();
    },
  }, "Remove from list");
  const ratingLabel = el("p", { class: "your-label" });
  const removeRated = el("button", {
    type: "button",
    class: "link-btn",
    onclick: async () => {
      if (await removeRating(movie)) refresh();
    },
  }, "Remove rating");
  const starGroup = stars(library.ratingOf(movie.id), async (n) => {
    const ok = await rateMovie(movie, n);
    if (ok) refresh();
    return ok;
  }, { label: `Your rating for ${movie.title}`, large: true });

  function refresh() {
    const status = library.statusOf(movie.id);
    const rating = library.ratingOf(movie.id);
    statusButtons.forEach((b, i) => b.setAttribute("aria-pressed", String(STATUSES[i].id === status)));
    removeListed.hidden = !status;
    starGroup.setValue(rating);
    ratingLabel.textContent = rating ? `You rated it ${rating}/5` : "Seen it? Rate it to improve your picks.";
    removeRated.hidden = !rating;
  }
  refresh();

  box.append(
    el("div", { class: "your-list-head" }, el("h2", { id: "your-list-title" }, "Your list"), removeListed),
    el("div", { class: "segmented", role: "group", "aria-label": "List status" }, statusButtons),
    el("h2", { class: "your-rating-title" }, "Your rating"),
    el("div", { class: "your-rating-row" }, starGroup, ratingLabel, removeRated)
  );
  return box;
}
