/*
 * HyperAdmin sidebar — collapsible nav groups and the desktop icon rail
 * (templates/_sidebar.html, docs/specs/navigation-and-list-ux.md "UI details").
 *
 * The server renders both states from cookies, so this only flips the markup
 * and writes the cookies back:
 *
 *  - ha-nav-collapsed: comma-separated slugs of the collapsed groups;
 *  - ha-sidebar-rail:  "1" while the sidebar is an icon rail, else "0".
 *
 * Both are SameSite=Lax and scoped to the admin path. Delegated on document,
 * so it works however late the script loads; without it the sidebar keeps
 * the state the server rendered.
 */

(function () {
  "use strict";

  if (window.hyperadminSidebar) return;
  window.hyperadminSidebar = true;

  var ONE_YEAR = 31536000;

  function setCookie(source, name, value) {
    var holder = source.closest("[data-ha-cookie-path]");
    var path = (holder && holder.getAttribute("data-ha-cookie-path")) || "/";
    try {
      document.cookie =
        name + "=" + encodeURIComponent(value) +
        "; Path=" + path + "; Max-Age=" + ONE_YEAR + "; SameSite=Lax";
    } catch (e) {
      // Cookies blocked: the state lasts until the next page load.
    }
  }

  function toggleGroup(button) {
    var group = button.closest(".ha-nav-group");
    var collapse = button.getAttribute("aria-expanded") !== "false";
    button.setAttribute("aria-expanded", collapse ? "false" : "true");
    if (group) group.classList.toggle("ha-nav-group--collapsed", collapse);
    var scope = button.closest("nav") || document;
    var slugs = [];
    scope.querySelectorAll('[data-ha-nav-group][aria-expanded="false"]').forEach(function (el) {
      slugs.push(el.getAttribute("data-ha-nav-group"));
    });
    setCookie(button, "ha-nav-collapsed", slugs.join(","));
  }

  function toggleRail(button) {
    var shell = button.closest("[data-collapsed]");
    if (!shell) return;
    var rail = shell.getAttribute("data-collapsed") !== "true";
    shell.setAttribute("data-collapsed", rail ? "true" : "false");
    button.setAttribute("aria-pressed", rail ? "true" : "false");
    setCookie(button, "ha-sidebar-rail", rail ? "1" : "0");
  }

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!target || !target.closest) return;
    var rail = target.closest("[data-ha-rail-toggle]");
    if (rail) {
      toggleRail(rail);
      return;
    }
    var group = target.closest("[data-ha-nav-group]");
    if (group) toggleGroup(group);
  });
})();
