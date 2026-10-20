import { api } from "../api.js";
import { go } from "../router.js";
import { library } from "../library.js";
import { el, errorBox, poster, skeletonGrid, toast } from "../ui.js";

const NEEDED = 3;

export async function renderWelcome(view) {
  document.body.classList.add("bare");
  const picked = new Map(library.loved().map((m) => [m.id, m]));
  const status = el("p", { class: "pick-count", "aria-live": "polite" });
  const next = el("button", { type: "button", class: "btn primary", onclick: finish }, "Show my picks");
  const gridHost = el("div", {}, skeletonGrid(18));

  const update = () => {
    const n = picked.size;
    status.textContent = n >= NEEDED ? `${n} picked. Add more or continue.` : `${n} of ${NEEDED} picked`;
    next.disabled = n < NEEDED;
  };

  view.replaceChildren(
    el(
      "section",
      { class: "welcome" },
      el("h1", {}, "Pick a few movies you love"),
      el("p", { class: "lede" }, `Tap at least ${NEEDED}. We'll use them to find what you should watch next.`),
      gridHost
    ),
    el(
      "div",
      { class: "pick-bar" },
      status,
      el("div", { class: "pick-actions" },
        el("button", { type: "button", class: "btn ghost", onclick: skip }, "Skip for now"),
        next
      )
    )
  );
  update();

  async function load() {
    try {
      const movies = await api.popular(48);
      gridHost.replaceChildren(
        el(
          "div",
          { class: "grid pick-grid" },
          movies.map((movie) => {
            const tile = el(
              "button",
              {
                type: "button",
                class: "pick",
                "aria-pressed": String(picked.has(movie.id)),
                onclick: () => {
                  picked.has(movie.id) ? picked.delete(movie.id) : picked.set(movie.id, movie);
                  tile.setAttribute("aria-pressed", String(picked.has(movie.id)));
                  update();
                },
              },
              poster(movie),
              el("span", { class: "pick-check", "aria-hidden": "true" }, "✓"),
              el("span", { class: "card-title" }, movie.title),
              el("span", { class: "card-meta" }, movie.year ?? "")
            );
            return tile;
          })
        )
      );
    } catch (error) {
      gridHost.replaceChildren(errorBox(error.message, load));
    }
  }

  async function finish() {
    next.disabled = true;
    next.textContent = "Saving…";
    const toSave = [...picked.values()].filter((m) => library.ratingOf(m.id) < 4);
    try {
      await Promise.all(toSave.map((m) => library.rate(m, 5)));
      go("#/");
    } catch (error) {
      toast(`Couldn't save your picks. ${error.message}`);
      next.textContent = "Show my picks";
      update();
    }
  }

  function skip() {
    library.skipWelcome();
    go("#/");
  }

  await load();
}
