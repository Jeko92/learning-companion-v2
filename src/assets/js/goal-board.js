/*
 * Drag and drop on the goal board (templates/goals/goal_list.html, "All" tab).
 *
 * An enhancement only: every card's Move menu is a plain POST form that works
 * without this script. Dropping a card in another column posts the column's
 * status to the card's goals:move URL (Accept: application/json, with the
 * CSRF token of the card's own form). On success the card's menu and the
 * column counts follow and the move is announced; on failure the card goes
 * back where it was and the error alert says why.
 *
 * Needs SortableJS (assets/js/vendor/sortable.min.js), loaded before it.
 */
(function () {
  "use strict";

  var board = document.querySelector("[data-board]");
  if (!board || typeof Sortable === "undefined") {
    return;
  }
  var announcer = document.querySelector("[data-board-announce]");
  var errorAlert = document.querySelector("[data-board-error]");
  var FALLBACK_ERROR = "Reload the page and try again.";

  function title(card) {
    return card.querySelector("a").textContent.trim();
  }

  // The column's count badge and its "No goals." note.
  function refresh(list) {
    var count = list.querySelectorAll("[data-goal]").length;
    var column = list.closest("[data-board-column]");
    column.querySelector("[data-board-count]").textContent = String(count);
    list.querySelector("[data-board-empty]").hidden = count > 0;
  }

  // The Move menu offers every status but the card's own.
  function syncMenu(card, status) {
    card.querySelectorAll('button[name="status"]').forEach(function (button) {
      button.hidden = button.value === status;
    });
  }

  function putBack(card, from, oldIndex) {
    var cards = from.querySelectorAll("[data-goal]");
    from.insertBefore(card, cards[oldIndex] || null);
  }

  function move(card, from, to, oldIndex) {
    errorAlert.hidden = true;
    refresh(from);
    refresh(to);
    var data = new FormData();
    data.append(
      "csrfmiddlewaretoken",
      card.querySelector('input[name="csrfmiddlewaretoken"]').value
    );
    data.append("status", to.dataset.status);
    fetch(card.dataset.moveUrl, {
      method: "POST",
      body: data,
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    })
      .then(function (response) {
        return response
          .json()
          .catch(function () {
            return {};
          })
          .then(function (body) {
            if (!response.ok) {
              throw new Error(body.error || FALLBACK_ERROR);
            }
            return body;
          });
      })
      .then(function (body) {
        syncMenu(card, body.status);
        announcer.textContent =
          "Moved “" + title(card) + "” to " + body.label + ".";
      })
      .catch(function (error) {
        putBack(card, from, oldIndex);
        refresh(from);
        refresh(to);
        // A network failure is a TypeError with the browser's own wording.
        var reason = error instanceof TypeError ? FALLBACK_ERROR : error.message;
        errorAlert.textContent =
          "Couldn't move “" + title(card) + "”. " + reason;
        errorAlert.hidden = false;
      });
  }

  board.querySelectorAll("[data-board-list]").forEach(function (list) {
    Sortable.create(list, {
      group: "goals",
      // Columns stay newest first: cards only move between columns.
      sort: false,
      draggable: "[data-goal]",
      // The Move menu stays clickable and never starts a drag.
      filter: "details",
      preventOnFilter: false,
      // On touch, a short hold starts a drag so the page still scrolls.
      delay: 150,
      delayOnTouchOnly: true,
      animation: 150,
      ghostClass: "board-ghost",
      onAdd: function (event) {
        move(event.item, event.from, event.to, event.oldIndex);
      },
    });
  });
})();
