// The console's page script (spec/plans/console-and-fleet-plan.md 3.4, route 1). Plain
// JavaScript, no framework, no network beyond this server. It does four things: follows the
// event stream and refreshes the live sections of the page in place (never a form being
// filled in); sorts a table by a clicked column; moves through the inbox from the keyboard;
// and submits the verdict form with Ctrl-Enter. Every page works without it, as it did
// before: this file only removes the meta refresh it replaces.
(function () {
  "use strict";

  // -- live sections -----------------------------------------------------------------------
  var refreshing = false, pending = false;
  function formBusy(section) {
    var active = document.activeElement;
    if (section.contains(active) && (active.tagName === "TEXTAREA" || active.tagName === "INPUT" || active.tagName === "SELECT")) return true;
    var areas = section.querySelectorAll("textarea");
    for (var i = 0; i < areas.length; i++) if (areas[i].value) return true;
    return false;
  }
  function refresh() {
    if (refreshing) { pending = true; return; }
    refreshing = true;
    fetch(location.pathname + location.search, { credentials: "same-origin", cache: "no-store" })
      .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
      .then(function (text) {
        var doc = new DOMParser().parseFromString(text, "text/html");
        var fresh = doc.querySelectorAll("[data-live]");
        for (var i = 0; i < fresh.length; i++) {
          var name = fresh[i].getAttribute("data-live");
          var old = document.querySelector('[data-live="' + name + '"]');
          if (!old || formBusy(old)) continue;
          var focused = document.activeElement && old.contains(document.activeElement) ? document.activeElement.getAttribute("href") : null;
          old.innerHTML = fresh[i].innerHTML;
          if (focused) { var again = old.querySelector('a[href="' + focused + '"]'); if (again) again.focus(); }
        }
        markFocus();
      })
      .catch(function () { /* the next event tries again; the page is still the last good one */ })
      .then(function () { refreshing = false; if (pending) { pending = false; setTimeout(refresh, 300); } });
  }
  var timer = null;
  function scheduleRefresh() { clearTimeout(timer); timer = setTimeout(refresh, 400); }

  var meta = document.querySelector('meta[http-equiv="refresh"]');
  if (meta && window.EventSource) {
    meta.parentNode.removeChild(meta);
    var source = new EventSource("/events");
    ["hold_opened", "hold_resolved", "run", "step", "delivery", "project"].forEach(function (name) {
      source.addEventListener(name, scheduleRefresh);
    });
    source.addEventListener("tick", scheduleRefresh);
    source.onerror = function () { /* EventSource reconnects by itself; the next tick refreshes */ };
  }

  // -- sortable tables -----------------------------------------------------------------------
  document.addEventListener("click", function (e) {
    var th = e.target.closest && e.target.closest("th");
    if (!th || th.closest("form")) return;
    var table = th.closest("table"); if (!table) return;
    var head = th.parentNode; if (head !== table.rows[0]) return;
    var col = Array.prototype.indexOf.call(head.children, th);
    var rows = Array.prototype.slice.call(table.rows, 1);
    var asc = th.getAttribute("data-sorted") !== "asc";
    rows.sort(function (a, b) {
      var A = (a.cells[col] || {}).textContent || "", B = (b.cells[col] || {}).textContent || "";
      var x = parseFloat(A), y = parseFloat(B);
      var c = (!isNaN(x) && !isNaN(y)) ? x - y : A.localeCompare(B);
      return asc ? c : -c;
    });
    rows.forEach(function (r) { table.appendChild(r); });
    Array.prototype.forEach.call(head.children, function (h) { h.removeAttribute("data-sorted"); });
    th.setAttribute("data-sorted", asc ? "asc" : "desc");
  });

  // -- figures: click to see one at its natural size, click again to shrink -----------------
  document.addEventListener("click", function (e) {
    var img = e.target.closest && e.target.closest("img.fig");
    if (!img) return;
    var on = img.classList.toggle("zoom");
    var grid = img.closest(".figs");
    if (grid) grid.classList.toggle("zoomed", on);
  });

  // -- the inbox from the keyboard -----------------------------------------------------------
  var cursor = -1;
  function cards() { return Array.prototype.slice.call(document.querySelectorAll("[data-card]")); }
  function markFocus() {
    var all = cards();
    all.forEach(function (c, i) { c.classList.toggle("focus", i === cursor); });
  }
  function typing(e) {
    var t = e.target;
    return t && (t.tagName === "TEXTAREA" || t.tagName === "INPUT" || t.tagName === "SELECT");
  }
  document.addEventListener("keydown", function (e) {
    if (e.ctrlKey && e.key === "Enter") {
      var form = document.querySelector("form[data-verdict]");
      if (form) { form.requestSubmit ? form.requestSubmit() : form.submit(); }
      return;
    }
    if (typing(e) || e.altKey || e.ctrlKey || e.metaKey) return;
    var all = cards();
    if (all.length && (e.key === "j" || e.key === "k")) {
      cursor = e.key === "j" ? Math.min(cursor + 1, all.length - 1) : Math.max(cursor - 1, 0);
      markFocus();
      all[cursor].scrollIntoView({ block: "nearest" });
      e.preventDefault();
    } else if (all.length && e.key === "Enter" && cursor >= 0) {
      var link = all[cursor].querySelector("a[data-open]");
      if (link) location.href = link.getAttribute("href");
    } else if (e.key === "a" || e.key === "r" || e.key === "d" || e.key === "o") {
      var want = { a: "accept", r: "reject", d: "defer", o: "override" }[e.key];
      var radio = document.querySelector('form[data-verdict] input[name="verdict"][value="' + want + '"]');
      if (radio) {
        radio.checked = true;
        var reason = document.querySelector('form[data-verdict] textarea[name="reason"]');
        if (reason) reason.focus();
        e.preventDefault();
      }
    }
  });
})();
