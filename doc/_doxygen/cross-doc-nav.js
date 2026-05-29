document.addEventListener("DOMContentLoaded", function () {
  if (!window.SAFETY_NAV_LINKS) return;

  var sideNav = document.getElementById("side-nav");
  var navTree = document.getElementById("nav-tree");
  if (!sideNav || !navTree) return;

  // Doxygen writes extra stylesheet links using $relpath^, so the href
  // attribute of the cross-doc-nav.css <link> is the relative path from the
  // current page back to the html/ root (e.g. "" at root, "../" one level in).
  var cssLink = document.querySelector('link[href$="cross-doc-nav.css"]');
  if (!cssLink) return;
  var relToHtmlRoot = cssLink.getAttribute("href").replace("cross-doc-nav.css", "");

  // From html/ go up two more levels to reach deploy/:
  //   html/ -> <site-dir>/ -> deploy/
  var prefix = relToHtmlRoot + "../../";

  // Detect the active entry using the absolute CSS URL, which contains the
  // current site directory name (e.g. "/doxygen-zephyr-safety-api/").
  var cssAbsHref = cssLink.href;
  function isActive(href) {
    if (/^https?:\/\//.test(href)) return false;
    var siteDir = href.split("/")[0];
    return cssAbsHref.indexOf("/" + siteDir + "/") !== -1;
  }

  // Build the nav widget.
  var nav = document.createElement("div");
  nav.id = "cross-doc-nav";

  window.SAFETY_NAV_LINKS.forEach(function (entry) {
    var a = document.createElement("a");
    a.textContent = entry.label;
    a.href = /^https?:\/\//.test(entry.href) ? entry.href : prefix + entry.href;
    if (isActive(entry.href)) a.classList.add("active");
    nav.appendChild(a);
  });

  sideNav.insertBefore(nav, navTree);
});
