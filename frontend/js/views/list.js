import { api } from "../api.js";
import { rateMovie, removeFromList, setStatus } from "../actions.js";
import { library, STATUSES } from "../library.js";
import { el, grid, stars } from "../ui.js";

const EMPTY = {
  all: "Your list is empty. Open any movie and add it to Plan to watch, or rate the ones you've seen.",
  watching: "Nothing in progress. Mark a movie as Watching from its page.",
  plan_to_watch: "Nothing planned yet. Add movies you want to see from their pages.",
  watched: "Rate a movie or mark it Watched and it shows up here.",
  dropped: "Movies you gave up on go here. They also teach your picks what you don't like.",
};

export function renderList(view, status) {
  const tab = STATUSES.some((s) => s.id === status) ? status : "all";
  document.title = "My list · Movie Picks";
  const statsHost = el("div", { class: "stats", "aria-live": "polite" });
  const body = el("div");
  view.replaceChildren(
    el(
      "section",
      { class: "page" },
      el("h1", { class: "page-title" }, "My list"),
      statsHost,
      el("nav", { class: "tabs", "aria-label": "Filter by status" }, tabs(tab)),
      body
    )
  );

  const draw = () => {
    const movies = tab === "all" ? [...library.entries.values()] : library.withStatus(tab);
    body.replaceChildren(
      movies.length
        ? grid(movies, { extra: controls })
        : el("div", { class: "empty" }, el("p", {}, EMPTY[tab]), el("a", { class: "btn primary", href: "#/" }, "Find movies"))
    );
    view.querySelector(".tabs").replaceChildren(...tabs(tab));
  };

  const controls = (m) => {
    const select = el(
      "select",
      { class: "status-select", "aria-label": `List status for ${m.title}` },
      STATUSES.map((s) => el("option", { value: s.id, selected: s.id === m.status }, s.label)),
      el("option", { value: "remove" }, "Remove from list")
    );
    select.addEventListener("change", async () => {
      const ok = select.value === "remove" ? await removeFromList(m) : await setStatus(m, select.value);
      if (!ok) select.value = m.status;
      draw();
      loadStats(statsHost);
    });
    return el(
      "div",
      { class: "list-controls" },
      select,
      stars(m.rating ?? 0, async (n) => {
        const ok = await rateMovie(m, n);
        if (ok) loadStats(statsHost);
        return ok;
      }, { label: `Your rating for ${m.title}` })
    );
  };

  draw();
  view.querySelector(".tab[aria-current=page]")?.scrollIntoView({ block: "nearest", inline: "nearest" });
  loadStats(statsHost);
}

function tabs(active) {
  const count = (id) => (id === "all" ? library.entries.size : library.withStatus(id).length);
  return [{ id: "all", label: "All" }, ...STATUSES].map((s) =>
    el(
      "a",
      { class: "tab", href: s.id === "all" ? "#/list" : `#/list?status=${s.id}`, "aria-current": s.id === active ? "page" : null },
      s.label,
      el("span", { class: "tab-count" }, count(s.id))
    )
  );
}

async function loadStats(host) {
  try {
    const s = await api.stats();
    const hours = s.minutesWatched / 60;
    const items = [
      [s.counts.watched, s.counts.watched === 1 ? "movie watched" : "movies watched"],
      [hours >= 10 ? Math.round(hours) : hours.toFixed(1).replace(/\.0$/, ""), "hours of film"],
      [s.averageRating ?? "–", "your average rating"],
      [s.counts.plan_to_watch, "on your watchlist"],
    ];
    host.replaceChildren(
      el("dl", { class: "stat-list" }, items.map(([value, label]) => el("div", { class: "stat" }, el("dt", {}, label), el("dd", {}, value)))),
      s.topGenres.length
        ? el("p", { class: "taste" }, "You watch mostly ", s.topGenres.map((g) => g.genre).join(", ").replace(/, ([^,]*)$/, " and $1"), ".")
        : ""
    );
  } catch {
    host.replaceChildren(); // stats are a bonus; the list itself still works
  }
}
