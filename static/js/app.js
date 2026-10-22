"use strict";
(() => {
  const launch = document.getElementById("chat-launch");
  const panel = document.getElementById("chat-panel");
  let chatLoaded = false;
  let chatLoading = false;
  function closeChat() {
    panel.hidden = true;
    launch.setAttribute("aria-expanded", "false");
    launch.focus();
  }
  if (launch && panel) {
    launch.addEventListener("click", () => {
      if (!panel.hidden) return closeChat();
      panel.hidden = false;
      launch.setAttribute("aria-expanded", "true");
      document.getElementById("chat-input").focus();
      if (chatLoaded || chatLoading) return;
      chatLoading = true;
      const status = document.getElementById("chat-status");
      const send = document.getElementById("chat-send");
      status.textContent = "Preparing the assistant…";
      send.disabled = true;
      const script = document.createElement("script");
      script.src = launch.dataset.chatScript;
      script.defer = true;
      script.onload = () => {
        chatLoaded = true;
        chatLoading = false;
        status.textContent = "Ready. Ask about the local research.";
        send.disabled = false;
      };
      script.onerror = () => {
        chatLoading = false;
        status.textContent = "The assistant could not load. Close and reopen it to retry.";
        script.remove();
      };
      document.head.append(script);
    });
    document.getElementById("chat-close").addEventListener("click", closeChat);
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && !panel.hidden) closeChat();
    });
    // Prevent a page navigation if the optional assistant script is still loading.
    document.getElementById("chat-form").addEventListener("submit", event => {
      if (!chatLoaded) event.preventDefault();
    });
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const motionControllers = [];

  // Each navigation owns one moving surface. Geometry is measured locally so
  // resizing, browser zoom, and horizontally scrolled tab lists stay aligned.
  function createMovingPill(container, items) {
    const pill = document.createElement("span");
    pill.className = "navigation-pill";
    pill.setAttribute("aria-hidden", "true");
    container.prepend(pill);
    container.classList.add("has-moving-pill");
    let selected = null;
    let frame = 0;
    function place(item, animate = true) {
      if (!item) return;
      selected = item;
      const box = item.getBoundingClientRect();
      const parent = container.getBoundingClientRect();
      pill.classList.toggle("pill-instant", !animate || reducedMotion.matches);
      pill.style.width = `${box.width}px`;
      pill.style.height = `${box.height}px`;
      pill.style.transform = `translate(${box.left - parent.left + container.scrollLeft - container.clientLeft}px, ${box.top - parent.top + container.scrollTop - container.clientTop}px)`;
      pill.classList.add("pill-visible");
    }
    function refresh() {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => place(selected, false));
    }
    if ("ResizeObserver" in window) {
      const observer = new ResizeObserver(refresh);
      observer.observe(container);
      items.forEach(item => observer.observe(item));
    }
    window.addEventListener("resize", refresh, {passive: true});
    window.addEventListener("pageshow", refresh);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(refresh);
    motionControllers.push(() => place(selected, false));
    return {place};
  }

  const mainNavigation = document.querySelector(".main-nav");
  if (mainNavigation) {
    const links = Array.from(mainNavigation.querySelectorAll("a[href]"));
    const current = links.find(link => link.getAttribute("aria-current") === "page");
    const indicator = createMovingPill(mainNavigation, links);
    let previous = null;
    // Store link identity, not pixel coordinates: the next page may have a
    // different account header or viewport width. Private browsing can deny storage.
    try {
      const saved = JSON.parse(sessionStorage.getItem("atlas-navigation") || "null");
      sessionStorage.removeItem("atlas-navigation");
      if (saved && saved.target === location.pathname && Date.now() - saved.at < 8000) {
        previous = links.find(link => new URL(link.href).pathname === saved.from);
      }
    } catch (_) { /* Navigation remains fully usable without session storage. */ }
    if (current) {
      indicator.place(reducedMotion.matches ? current : (previous || current), false);
      if (previous && previous !== current && !reducedMotion.matches) {
        requestAnimationFrame(() => requestAnimationFrame(() => indicator.place(current)));
      }
    }
    window.addEventListener("pageshow", event => {
      if (event.persisted && current) indicator.place(current, false);
    });
    links.forEach(link => {
      link.addEventListener("click", event => {
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const destination = new URL(link.href);
        if (destination.origin !== location.origin) return;
        try {
          sessionStorage.setItem("atlas-navigation", JSON.stringify({
            from: current ? new URL(current.href).pathname : location.pathname,
            target: destination.pathname,
            at: Date.now()
          }));
        } catch (_) { /* Storage is optional. */ }
        indicator.place(link);
      });
    });
  }

  document.querySelectorAll("[data-tabs]").forEach(root => {
    const tablist = root.querySelector("[data-tablist]");
    if (!tablist) return;
    const tabs = Array.from(tablist.querySelectorAll("[data-tab]"));
    const panels = Array.from(root.querySelectorAll("[data-panel]"));
    const indicator = createMovingPill(tablist, tabs);
    const animations = new Map();
    let activeId = null;
    tablist.setAttribute("role", "tablist");
    tablist.setAttribute("aria-orientation", "horizontal");
    function stopAnimations() {
      animations.forEach(animation => animation.cancel());
      animations.clear();
    }
    motionControllers.push(stopAnimations);
    function revealTab(tab) {
      const left = tab.offsetLeft;
      const right = left + tab.offsetWidth;
      if (left < tablist.scrollLeft + 6) tablist.scrollLeft = Math.max(0, left - 6);
      else if (right > tablist.scrollLeft + tablist.clientWidth - 6) tablist.scrollLeft = right - tablist.clientWidth + 6;
    }
    function activate(id, updateURL = false, focus = false) {
      const selected = tabs.find(tab => tab.dataset.tab === id) || tabs[0];
      if (!selected) return;
      const selectedId = selected.dataset.tab;
      const changed = activeId !== selectedId;
      if (!changed) {
        if (focus) selected.focus({preventScroll: true});
        return;
      }
      const animate = activeId !== null && !reducedMotion.matches;
      stopAnimations();
      tabs.forEach(tab => {
        const active = tab === selected;
        tab.id = `tab-${tab.dataset.tab}`;
        tab.setAttribute("role", "tab");
        tab.setAttribute("aria-controls", tab.dataset.tab);
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
      });
      panels.forEach(panel => {
        const active = panel.dataset.panel === selectedId;
        panel.hidden = !active;
        panel.setAttribute("role", "tabpanel");
        panel.setAttribute("aria-labelledby", `tab-${panel.dataset.panel}`);
        panel.tabIndex = 0;
        if (active && animate && typeof panel.animate === "function") {
          const animation = panel.animate([
            {opacity: 0.35, transform: "translateY(9px)"},
            {opacity: 1, transform: "translateY(0)"}
          ], {duration: 250, easing: "cubic-bezier(.22,.8,.25,1)"});
          animations.set(panel, animation);
          animation.onfinish = () => animations.delete(panel);
        }
      });
      indicator.place(selected, animate);
      revealTab(selected);
      activeId = selectedId;
      if (updateURL && location.hash !== `#${selectedId}`) history.pushState(null, "", `#${selectedId}`);
      if (focus) selected.focus({preventScroll: true});
      if (changed) root.dispatchEvent(new CustomEvent("atlas:tab", {bubbles: true, detail: {id: selectedId}}));
    }
    tabs.forEach((tab, index) => {
      tab.addEventListener("click", event => { event.preventDefault(); activate(tab.dataset.tab, true); });
      tab.addEventListener("keydown", event => {
        let next;
        if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
        else if (event.key === "ArrowLeft") next = (index + tabs.length - 1) % tabs.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        else return;
        event.preventDefault();
        activate(tabs[next].dataset.tab, true, true);
      });
    });
    root.addEventListener("click", event => {
      const link = event.target.closest('a[href^="#"]');
      if (!link || link.hasAttribute("data-tab")) return;
      const id = link.getAttribute("href").slice(1);
      if (!tabs.some(tab => tab.dataset.tab === id)) return;
      event.preventDefault();
      activate(id, true, true);
    });
    window.addEventListener("hashchange", () => activate(location.hash.slice(1)));
    window.addEventListener("popstate", () => activate(location.hash.slice(1)));
    activate(location.hash.slice(1));
  });
  reducedMotion.addEventListener("change", () => motionControllers.forEach(update => update()));

  const localToday = new Date();
  const dateMaximum = `${localToday.getFullYear()}-${String(localToday.getMonth() + 1).padStart(2, "0")}-${String(localToday.getDate()).padStart(2, "0")}`;
  document.querySelectorAll("[data-max-today]").forEach(input => { input.max = dateMaximum; });
  document.querySelectorAll("[data-submit-form]").forEach(form => {
    form.addEventListener("submit", () => {
      if (!form.checkValidity()) return;
      const button = form.querySelector('button[type="submit"]');
      if (!button) return;
      button.dataset.originalText = button.textContent;
      button.disabled = true;
      button.textContent = "Saving…";
      form.setAttribute("aria-busy", "true");
    });
  });
  window.addEventListener("pageshow", () => {
    document.querySelectorAll("[data-submit-form]").forEach(form => {
      form.removeAttribute("aria-busy");
      const button = form.querySelector('button[type="submit"]');
      if (button && button.dataset.originalText) {
        button.disabled = false;
        button.textContent = button.dataset.originalText;
      }
    });
  });

  const form = document.querySelector(".loan-form");
  if (!form) return;
  const story = form.elements.description;
  const photo = form.elements.description_image;
  const submit = form.querySelector("button[type=submit]");
  const status = document.getElementById("form-status");
  const required = Array.from(form.querySelectorAll("[required]"));
  const originalLabel = submit.textContent;
  const birthDate = form.elements.dob;
  if (birthDate) {
    const today = new Date();
    birthDate.max = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  }
  function updateProgress() {
    const completed = required.filter(field => field.value.trim() && field.validity.valid).length;
    const hasStory = Boolean(story.value.trim() || photo.files.length);
    const total = required.length + 1;
    const value = completed + Number(hasStory);
    document.getElementById("form-progress").value = Math.round(value / total * 100);
    document.getElementById("form-progress-label").textContent = `${value} of ${total} required fields complete`;
  }
  function clearStoryError() {
    story.setCustomValidity("");
    photo.setCustomValidity("");
    updateProgress();
  }
  form.addEventListener("input", updateProgress);
  form.addEventListener("change", updateProgress);
  story.addEventListener("input", clearStoryError);
  photo.addEventListener("change", () => {
    clearStoryError();
    if (photo.files.length && photo.files[0].size > 8 * 1024 * 1024) {
      photo.setCustomValidity("Choose an image smaller than 8 MB.");
      photo.reportValidity();
    }
  });
  form.addEventListener("submit", event => {
    if (!story.value.trim() && !photo.files.length) {
      event.preventDefault();
      story.setCustomValidity("Enter the business story or upload an image.");
      story.reportValidity();
      return;
    }
    if (!form.checkValidity()) {
      event.preventDefault();
      form.reportValidity();
      return;
    }
    submit.disabled = true;
    submit.textContent = "Preparing assessment…";
    form.setAttribute("aria-busy", "true");
    status.textContent = photo.files.length ? "Reading the image and preparing your assessment. OCR can take longer than typed text." : "Analyzing the story and preparing your reports…";
  });
  window.addEventListener("pageshow", () => {
    submit.disabled = false;
    submit.textContent = originalLabel;
    form.removeAttribute("aria-busy");
    status.textContent = "";
  });
  updateProgress();
})();
