import { api } from "../api.js";
import { el, errorBox, grid, skeletonGrid } from "../ui.js";

export async function renderSearch(view, query) {
  const heading = el("h1", { class: "page-title" }, query ? `Results for “${query}”` : "Search");
  if (!query) {
    view.replaceChildren(el("section", { class: "page" }, heading, el("p", { class: "empty" }, "Type a movie title in the search box above, like “matrix” or “toy story”.")));
    return;
  }
  view.replaceChildren(el("section", { class: "page" }, heading, skeletonGrid(12)));
  try {
    const results = await api.search(query);
    view.replaceChildren(
      el(
        "section",
        { class: "page" },
        heading,
        results.length
          ? grid(results)
          : el("p", { class: "empty" }, `No movies match “${query}”. Try a shorter part of the title.`)
      )
    );
  } catch (error) {
    view.replaceChildren(el("section", { class: "page" }, heading, errorBox(`Search failed. ${error.message}`, () => renderSearch(view, query))));
  }
}
