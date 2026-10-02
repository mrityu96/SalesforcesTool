(function () {
  "use strict";

  const runtime = window.CmlRuntime || {};
  const extensionTransport = runtime.transport === "extension"
    && typeof chrome !== "undefined"
    && chrome.runtime
    && chrome.runtime.sendMessage;
  const apiBase = String(runtime.apiBase || "").replace(/\/$/, "");
  const tokenElement = document.querySelector('meta[name="cml-csrf-token"]');
  const metaToken = tokenElement ? String(tokenElement.content || "") : "";
  let csrfToken = (
    metaToken && metaToken !== "__CML_CSRF_TOKEN__"
  ) ? metaToken : "";
  let csrfPromise = null;

  function apiUrl(path) {
    if (!path) {
      return apiBase || "/";
    }
    if (/^https?:\/\//i.test(path)) {
      return path;
    }
    return apiBase + path;
  }

  async function parseJsonResponse(response) {
    const text = await response.text();
    try {
      return JSON.parse(text);
    } catch (_) {
      return {
        error: `Unexpected server response (HTTP ${response.status}):\n${text.slice(0, 500)}`,
        ok: false,
        log: `Server returned an unexpected response (HTTP ${response.status}):\n${text.slice(0, 500)}`,
      };
    }
  }

  async function extensionRequest(method, path, payload, options) {
    const signal = options && options.signal;
    if (signal && signal.aborted) {
      throw { aborted: true };
    }
    const operationId = payload && payload.operationId;
    function cancelIfPossible() {
      if (!operationId) {
        return;
      }
      chrome.runtime.sendMessage({
        type: "cml-api",
        method: "POST",
        path: "/api/operation/cancel",
        body: { operationId: operationId },
      });
    }
    if (signal && operationId) {
      signal.addEventListener("abort", cancelIfPossible, { once: true });
    }
    let response;
    try {
      response = await chrome.runtime.sendMessage({
        type: "cml-api",
        method: method,
        path: path,
        body: payload || {},
      });
    } catch (_) {
      throw { conn: true };
    } finally {
      if (signal && operationId) {
        signal.removeEventListener("abort", cancelIfPossible);
      }
    }
    if (signal && signal.aborted) {
      throw { aborted: true };
    }
    if (response == null) {
      throw { conn: true };
    }
    return response;
  }

  async function ensureCsrfToken() {
    if (extensionTransport) {
      return "browser-session";
    }
    if (csrfToken) {
      return csrfToken;
    }
    if (!csrfPromise) {
      csrfPromise = (async () => {
        let response;
        try {
          response = await fetch(apiUrl("/api/ping"), { cache: "no-store" });
        } catch (_) {
          throw { conn: true };
        }
        const payload = await parseJsonResponse(response);
        csrfToken = payload.localRequestToken || "";
        if (!csrfToken) {
          throw { conn: true };
        }
        return csrfToken;
      })();
    }
    try {
      return await csrfPromise;
    } catch (error) {
      csrfPromise = null;
      throw error;
    }
  }

  async function apiGet(path) {
    if (extensionTransport) {
      return extensionRequest("GET", path);
    }
    let response;
    try {
      response = await fetch(apiUrl(path), { cache: "no-store" });
    } catch (_) {
      throw { conn: true };
    }
    return parseJsonResponse(response);
  }

  async function postJSON(url, payload, options = {}) {
    if (extensionTransport) {
      return extensionRequest("POST", url, payload, options);
    }
    await ensureCsrfToken();
    let response;
    try {
      response = await fetch(apiUrl(url), {
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
    return parseJsonResponse(response);
  }

  window.CmlApi = Object.freeze({ apiGet, postJSON, apiUrl });
})();
