/* Client-side fuzzy + synonym search for the Indriya docs.
 *
 * Loaded ONLY on the search results page (see _templates/search.html), which
 * also loads the vendored MiniSearch engine (_static/minisearch.js) and sets
 * window.FUZZY_INDEX_URL to the build-time index (_static/search_index.json,
 * emitted by conf.py).
 *
 * Two things the stock Sphinx search can't do, layered here:
 *   1. Typo tolerance  — MiniSearch fuzzy matching ("firmwre" -> "firmware").
 *   2. Acronym/synonym — a curated bidirectional map so "ble" surfaces
 *      Bluetooth pages and "dfu" surfaces "firmware update" pages (and back).
 *
 * House style mirrors _static/collapsible.js: vanilla JS, IIFE, no deps, work
 * deferred to DOMContentLoaded, theming via CSS custom properties.
 */
(function () {
  "use strict";

  /* Acronym / synonym clusters. Each array is an equivalence set: typing any
   * member expands the query to include every member of its cluster, so the
   * relationship is bidirectional for free (ble<->bluetooth, dfu<->firmware).
   * Multi-word entries ("firmware update") are tokenized on compile, so they
   * match MiniSearch's own tokenization of the indexed text. Keep this list
   * curated to the SDK's real vocabulary — it needs no rebuild to edit. */
  var CLUSTERS = [
    ["ble", "bluetooth", "bleak"],
    ["dfu", "firmware update", "mcumgr", "smp", "ota"],
    ["emg", "electromyography"],
    ["imu", "inertial", "accelerometer", "gyroscope"],
    ["ppg", "photoplethysmography"],
    ["usb", "cdc", "serial"],
    ["odr", "sample rate", "sampling rate"],
    ["auth", "sign in", "signin", "login", "account"],
    ["license", "licensing", "tier", "free", "plus", "pro"],
    ["recording", "storage", "sd card", "mrec"],
    ["encryption", "encrypt", "ecies", "aes", "decrypt"],
    ["delegate", "callback", "callbacks"],
  ];

  function tokenize(text) {
    return String(text || "")
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter(Boolean);
  }

  /* Compile the clusters into a token -> Set(all cluster tokens) lookup. */
  function compileSynonyms(clusters) {
    var map = new Map();
    clusters.forEach(function (cluster) {
      var tokens = new Set();
      cluster.forEach(function (member) {
        tokenize(member).forEach(function (t) { tokens.add(t); });
      });
      tokens.forEach(function (t) {
        var set = map.get(t);
        if (!set) { set = new Set(); map.set(t, set); }
        tokens.forEach(function (x) { set.add(x); });
      });
    });
    return map;
  }

  /* Expand a raw query into original tokens + any synonym-cluster tokens. */
  function expandQuery(query, synonyms) {
    var out = new Set();
    tokenize(query).forEach(function (token) {
      out.add(token);
      var extra = synonyms.get(token);
      if (extra) { extra.forEach(function (x) { out.add(x); }); }
    });
    return Array.from(out);
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* Build a short text snippet centered on the first matched term, with the
   * matched terms wrapped for highlighting. `terms` are lowercase tokens. */
  function makeSnippet(text, terms) {
    if (!text) { return ""; }
    var lower = text.toLowerCase();
    var at = -1;
    terms.forEach(function (term) {
      var i = lower.indexOf(term);
      if (i !== -1 && (at === -1 || i < at)) { at = i; }
    });
    var start = at === -1 ? 0 : Math.max(0, at - 70);
    var slice = text.slice(start, start + 240);
    var html = escapeHtml(slice);
    // Highlight longest terms first so "firmware" wins over "firm".
    terms.slice().sort(function (a, b) { return b.length - a.length; })
      .forEach(function (term) {
        if (term.length < 2) { return; }
        var re = new RegExp("(" + term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi");
        html = html.replace(re, '<em class="fuzzy-result-match">$1</em>');
      });
    return (start > 0 ? "… " : "") + html + " …";
  }

  function render(results, query, container, status) {
    container.innerHTML = "";
    if (!query) {
      status.textContent = "Type to search the documentation.";
      return;
    }
    if (!results.length) {
      status.textContent = 'No results for “' + query + '”.';
      return;
    }
    status.textContent =
      results.length + (results.length === 1 ? " result" : " results") +
      ' for “' + query + '”.';

    var list = document.createElement("ul");
    list.className = "fuzzy-search-results-list";
    results.forEach(function (r) {
      var li = document.createElement("li");
      li.className = "fuzzy-search-result";
      var link = document.createElement("a");
      link.className = "fuzzy-result-title";
      link.href = r.url;
      link.textContent = r.title || r.url;
      li.appendChild(link);
      var snippet = makeSnippet(r.text, r.terms || []);
      if (snippet) {
        var p = document.createElement("p");
        p.className = "fuzzy-result-snippet";
        p.innerHTML = snippet;
        li.appendChild(p);
      }
      list.appendChild(li);
    });
    container.appendChild(list);
  }

  function getQueryParam() {
    try {
      return new URLSearchParams(window.location.search).get("q") || "";
    } catch (e) {
      return "";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var input = document.getElementById("fuzzy-search-input");
    var container = document.getElementById("fuzzy-search-results");
    var status = document.getElementById("fuzzy-search-status");
    if (!container || !status) { return; }

    if (typeof window.MiniSearch !== "function") {
      status.textContent = "Search engine failed to load.";
      return;
    }

    var synonyms = compileSynonyms(CLUSTERS);
    var byId = new Map();
    var mini = new window.MiniSearch({
      idField: "id",
      fields: ["title", "text"],
      storeFields: ["title", "url"]
    });

    /* Short tokens (<=3 chars) are matched exactly: a 3-letter acronym like
     * "ble" or "dfu" must NOT fuzzy/prefix-match common words ("enabled",
     * "default"), which would flood the results. Longer terms get typo
     * tolerance (fuzzy) and as-you-type prefix matching. */
    var searchOpts = {
      combineWith: "OR",
      fuzzy: function (term) { return term.length > 3 ? 0.2 : false; },
      prefix: function (term) { return term.length > 3; },
      boost: { title: 3 }
    };

    function run(query) {
      var trimmed = (query || "").trim();
      if (!trimmed) { render([], "", container, status); return; }
      var expanded = expandQuery(trimmed, synonyms).join(" ");
      var hits = mini.search(expanded, searchOpts).slice(0, 40).map(function (h) {
        var doc = byId.get(h.id) || {};
        return { url: h.url, title: h.title, text: doc.text || "", terms: h.terms };
      });
      render(hits, trimmed, container, status);
    }

    status.textContent = "Loading search index…";
    fetch(window.FUZZY_INDEX_URL, { cache: "no-cache" })
      .then(function (resp) {
        if (!resp.ok) { throw new Error("HTTP " + resp.status); }
        return resp.json();
      })
      .then(function (docs) {
        docs.forEach(function (d) { byId.set(d.id, d); });
        mini.addAll(docs);

        var initial = getQueryParam();
        if (input) {
          input.value = initial;
          var timer = null;
          input.addEventListener("input", function () {
            if (timer) { clearTimeout(timer); }
            timer = setTimeout(function () {
              var q = input.value;
              run(q);
              try {
                var url = q
                  ? "?q=" + encodeURIComponent(q)
                  : window.location.pathname;
                window.history.replaceState(null, "", url);
              } catch (e) { /* history unavailable — ignore */ }
            }, 120);
          });
        }
        run(initial);
      })
      .catch(function (err) {
        status.textContent = "Could not load the search index.";
        if (window.console) { console.error("[fuzzy-search]", err); }
      });
  });
})();
