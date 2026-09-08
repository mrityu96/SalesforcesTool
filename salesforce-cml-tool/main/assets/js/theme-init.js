(function () {
  "use strict";
  try {
    document.documentElement.dataset.theme =
      localStorage.getItem("cml-theme") || "light";
  } catch (_) {
    document.documentElement.dataset.theme = "light";
  }
})();
