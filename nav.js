// The page menu at the top right of every page. The list of pages lives only
// here: add a page by adding a line, and include
// <script src="nav.js" defer></script> in the new page's <head>.

(function () {
  var pages = [
    ["index.html", "Spiral experiments"],
    ["procedure.html", "Procedure"],
    ["card.html", "Simulated card: results"],
    ["considered.html", "Considered and dropped"],
    ["spacing.html", "Ring spacing (FFT)"],
    ["explain.html", "Ring spacing: the controls"],
    ["center.html", "Center from chunks"],
    ["card_js.html", "Card in the browser (frozen)"],
  ];
  var here = location.pathname.split("/").pop() || "index.html";
  var menu = document.createElement("select");
  menu.id = "pageMenu";
  menu.setAttribute("aria-label", "Go to page");
  pages.forEach(function (page) {
    var option = new Option(page[1], page[0], false, page[0] === here);
    menu.add(option);
  });
  menu.onchange = function () { location.href = menu.value; };
  var style = document.createElement("style");
  style.textContent =
    "#pageMenu { position: absolute; top: 10px; right: 12px; z-index: 1000; " +
    "background: #222; color: #ddd; border: 1px solid #555; border-radius: 4px; " +
    "padding: 4px 6px; font: 14px system-ui, sans-serif; cursor: pointer; }" +
    "#pageMenu:hover { border-color: #888; }";
  document.head.appendChild(style);
  document.body.appendChild(menu);
})();
