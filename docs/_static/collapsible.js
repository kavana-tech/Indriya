/* Collapsible source blocks for the Examples page.
 *
 * Sphinx renders ``.. container:: collapsible-code`` as
 *   <div class="collapsible-code docutils container"> ... </div>
 * wrapping a captioned literalinclude. We move that content into a native
 * <details> element so it collapses with no framework and no extra Sphinx
 * extension. The literalinclude's :caption: becomes the clickable summary. */
(function () {
  "use strict";

  function makeCollapsible(box) {
    var details = document.createElement("details");
    details.className = "example-source";
    // Collapsed by default: we intentionally do NOT set `details.open`.

    var summary = document.createElement("summary");
    var caption = box.querySelector(".code-block-caption");
    // Use only the caption *text* — the caption div also holds a headerlink
    // glyph we don't want leaking into the summary label.
    var captionText = box.querySelector(".caption-text");
    if (caption) {
      var text = (captionText ? captionText.textContent : caption.textContent).trim();
      summary.textContent = text ? "Source: " + text : "Show source";
      caption.parentNode.removeChild(caption);
    } else {
      summary.textContent = "Show source";
    }
    details.appendChild(summary);

    while (box.firstChild) {
      details.appendChild(box.firstChild);
    }
    box.appendChild(details);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var boxes = document.querySelectorAll(".collapsible-code");
    Array.prototype.forEach.call(boxes, makeCollapsible);
  });
})();
