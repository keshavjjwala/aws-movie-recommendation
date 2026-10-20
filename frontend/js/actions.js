// List and rating actions with user feedback. Return false on failure so callers can roll back.
import { library, statusLabel } from "./library.js";
import { toast } from "./ui.js";

async function attempt(action, success, failure) {
  try {
    await action();
    toast(success);
    return true;
  } catch (error) {
    toast(`${failure} ${error.message}`);
    return false;
  }
}

export const rateMovie = (movie, rating) =>
  attempt(() => library.rate(movie, rating), `Rated ${movie.title} ${rating}/5. Your picks are updated.`, "Couldn't save your rating.");

export const removeRating = (movie) =>
  attempt(() => library.unrate(movie), `Removed your rating for ${movie.title}.`, "Couldn't remove the rating.");

export function setStatus(movie, status) {
  const verb = library.statusOf(movie.id) ? "Moved" : "Added";
  return attempt(() => library.setStatus(movie, status), `${verb} ${movie.title} to ${statusLabel(status)}.`, "Couldn't update your list.");
}

export const removeFromList = (movie) =>
  attempt(() => library.remove(movie), `Removed ${movie.title} from your list.`, "Couldn't update your list.");
