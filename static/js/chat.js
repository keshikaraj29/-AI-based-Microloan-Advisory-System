"use strict";
(() => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const log = document.getElementById("chat-log");
  const send = document.getElementById("chat-send");
  const status = document.getElementById("chat-status");
  let busy = false;
  function addMessage(text, role, metadata, actions) {
    const message = document.createElement("div");
    message.className = `chat-message ${role}`;
    message.textContent = text;
    if (metadata) {
      const source = document.createElement("small");
      source.textContent = metadata;
      message.append(source);
    }
    if (Array.isArray(actions)) {
      const cards = document.createElement("div");
      cards.className = "chat-action-cards";
      actions.slice(0, 4).forEach(action => {
        if (!action || typeof action.url !== "string" || typeof action.label !== "string") return;
        let url;
        try { url = new URL(action.url, location.origin); } catch { return; }
        if (url.origin !== location.origin || !/^\/(?:research|apply|applications(?:\/[a-zA-Z0-9-]+(?:\/(?:assessment|explanation))?)?|login|register)\/?$/.test(url.pathname)) return;
        const link = document.createElement("a");
        link.href = url.pathname + url.search + url.hash;
        link.textContent = `${action.label} →`;
        if (/\/explanation$/.test(url.pathname)) { link.target = "_blank"; link.rel = "noopener"; }
        cards.append(link);
      });
      if (cards.children.length) message.append(cards);
    }
    log.append(message);
    log.scrollTop = log.scrollHeight;
  }
  async function ask(question) {
    if (busy || !question.trim()) return;
    busy = true;
    send.disabled = true;
    input.disabled = true;
    form.setAttribute("aria-busy", "true");
    document.querySelectorAll("[data-chat-prompt]").forEach(button => { button.disabled = true; });
    addMessage(question, "user");
    input.value = "";
    status.textContent = "Looking up the local project…";
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]').content},
        body: JSON.stringify({message: question, application_id: document.querySelector('meta[name="application-id"]')?.content || undefined}),
        signal: controller.signal,
        credentials: "same-origin"
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "The assistant could not answer. Please try again.");
      if (typeof data.reply !== "string" || !data.reply.trim()) throw new Error("No response was returned. Please try again.");
      const elapsed = Number(data.elapsed_ms);
      const detail = [data.source || "Local project", Number.isFinite(elapsed) ? (elapsed < 1 ? "<1 ms server time" : `${Math.round(elapsed)} ms server time`) : ""].filter(Boolean).join(" · ");
      addMessage(data.reply, "assistant", detail, data.actions);
      status.textContent = "Response ready.";
    } catch (error) {
      status.textContent = error.name === "AbortError" ? "The request took too long. Please try again." : error.message;
      input.value = question;
    } finally {
      window.clearTimeout(timeout);
      busy = false;
      send.disabled = false;
      input.disabled = false;
      form.removeAttribute("aria-busy");
      document.querySelectorAll("[data-chat-prompt]").forEach(button => { button.disabled = false; });
      if (!document.getElementById("chat-panel").hidden) input.focus();
    }
  }
  form.addEventListener("submit", event => {
    event.preventDefault();
    ask(input.value.trim());
  });
  document.querySelectorAll("[data-chat-prompt]").forEach(button => {
    button.addEventListener("click", () => ask(button.dataset.chatPrompt));
  });
})();
