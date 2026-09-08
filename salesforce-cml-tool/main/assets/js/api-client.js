(function () {
  "use strict";

  const tokenElement = document.querySelector('meta[name="cml-csrf-token"]');
  const csrfToken = tokenElement ? tokenElement.content : "";

  async function apiGet(path) {
    let response;
    try {
      response = await fetch(path, { cache: "no-store" });
    } catch (_) {
      throw { conn: true };
    }
    const text = await response.text();
    try {
      return JSON.parse(text);
    } catch (_) {
      return {
        error: `Unexpected server response (HTTP ${response.status}):\n${text.slice(0, 500)}`,
      };
    }
  }

  async function postJSON(url, payload, options = {}) {
    let response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CML-CSRF": csrfToken,
        },
        body: JSON.stringify(payload),
        signal: options.signal,
      });
    } catch (error) {
      if (error && error.name === "AbortError") throw { aborted: true };
      throw { conn: true };
    }
    const text = await response.text();
    try {
      return JSON.parse(text);
    } catch (_) {
      return {
        ok: false,
        log: `Server returned an unexpected response (HTTP ${response.status}):\n${text.slice(0, 500)}`,
      };
    }
  }

  window.CmlApi = Object.freeze({ apiGet, postJSON });
})();
