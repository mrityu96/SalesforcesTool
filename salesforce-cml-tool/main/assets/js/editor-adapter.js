(function () {
  "use strict";

  if (!window.CmlCodeMirror) {
    throw new Error("The local CodeMirror bundle did not initialize.");
  }

  const nonce = document.querySelector(
    'meta[name="cml-csrf-token"]')?.content || "";
  const instances = new Map();

  function create(hostOrId, options) {
    const host = typeof hostOrId === "string"
      ? document.getElementById(hostOrId) : hostOrId;
    if (!host) throw new Error("CodeMirror host was not found.");
    if (instances.has(host)) return instances.get(host);

    const config = options || {};
    let suppressInput = false;
    const view = window.CmlCodeMirror.create({
      parent: host,
      nonce,
      placeholder: config.placeholder || "",
      onChange() {
        if (suppressInput) return;
        host.dispatchEvent(new Event("input", { bubbles: true }));
        if (typeof config.onChange === "function") config.onChange(adapter.getValue());
      },
    });

    const adapter = {
      getValue: () => view.state.doc.toString(),
      setValue(value, emitInput) {
        const text = value == null ? "" : String(value);
        suppressInput = true;
        view.dispatch({
          changes: { from: 0, to: view.state.doc.length, insert: text },
          selection: { anchor: 0 },
        });
        suppressInput = false;
        if (emitInput !== false) host.dispatchEvent(new Event("input", { bubbles: true }));
      },
      getSelection: () => view.state.selection.main,
      setSelection(anchor, head) {
        const length = view.state.doc.length;
        const safeAnchor = Math.max(0, Math.min(length, Number(anchor) || 0));
        const safeHead = Math.max(0, Math.min(
          length, head == null ? safeAnchor : Number(head) || 0));
        view.dispatch({ selection: { anchor: safeAnchor, head: safeHead } });
      },
      replaceRange(from, to, text, selectReplacement) {
        const length = view.state.doc.length;
        const start = Math.max(0, Math.min(length, Number(from) || 0));
        const end = Math.max(start, Math.min(length, Number(to) || 0));
        const replacement = String(text == null ? "" : text);
        const selection = selectReplacement
          ? { anchor: start, head: start + replacement.length }
          : { anchor: start + replacement.length };
        view.dispatch({ changes: { from: start, to: end, insert: replacement }, selection });
      },
      focus: () => view.focus(),
      selectAll() {
        view.dispatch({ selection: { anchor: 0, head: view.state.doc.length } });
        view.focus();
      },
      goToLine(line) {
        const number = Math.max(1, Math.min(view.state.doc.lines, Number(line) || 1));
        const position = view.state.doc.line(number).from;
        const effects = window.CmlCodeMirror.EditorView
          ? window.CmlCodeMirror.EditorView.scrollIntoView(position, { y: "center" })
          : undefined;
        view.dispatch({ selection: { anchor: position }, effects });
        view.focus();
      },
      setDiagnostics(diagnostics) {
        const length = view.state.doc.length;
        const normalized = (diagnostics || []).map(item => {
          const from = Math.max(0, Math.min(length, Number(item.from) || 0));
          const to = Math.max(from, Math.min(
            length, item.to == null ? from : Number(item.to) || 0));
          return {
            from,
            to: to > from ? to : Math.min(length, from + 1),
            severity: ["error", "warning", "info"].includes(item.severity)
              ? item.severity : "info",
            message: String(item.message || "CML guidance"),
            source: item.source ? String(item.source) : "CML Tool",
          };
        });
        window.CmlCodeMirror.applyDiagnostics(view, normalized);
      },
      get scrollTop() { return view.scrollDOM.scrollTop; },
      set scrollTop(value) { view.scrollDOM.scrollTop = Number(value) || 0; },
      get scrollLeft() { return view.scrollDOM.scrollLeft; },
      set scrollLeft(value) { view.scrollDOM.scrollLeft = Number(value) || 0; },
      view,
      host,
    };

    Object.defineProperties(host, {
      value: { configurable: true, get: adapter.getValue, set: value => adapter.setValue(value) },
      selectionStart: {
        configurable: true,
        get: () => adapter.getSelection().from,
        set: value => adapter.setSelection(value, adapter.getSelection().to),
      },
      selectionEnd: {
        configurable: true,
        get: () => adapter.getSelection().to,
        set: value => adapter.setSelection(adapter.getSelection().from, value),
      },
      scrollTop: {
        configurable: true,
        get: () => adapter.scrollTop,
        set: value => { adapter.scrollTop = value; },
      },
      scrollLeft: {
        configurable: true,
        get: () => adapter.scrollLeft,
        set: value => { adapter.scrollLeft = value; },
      },
    });
    host.setSelectionRange = (start, end) => adapter.setSelection(start, end);
    host.setRangeText = (text, start, end) => adapter.replaceRange(start, end, text, true);
    host.select = () => adapter.selectAll();
    host.focus = () => adapter.focus();
    instances.set(host, adapter);
    return adapter;
  }

  window.CmlEditors = { create, instances };
  window.cmlEditor = create("content", {
    placeholder: "Fetched CML appears here. You can also paste CML and deploy it.",
  });
  window.targetDraftEditor = create("tgtEditArea", {
    placeholder: "Edit the complete target CML working draft.",
  });
})();
