// Interactive review page: decision choices, reject reasons, preview controls, link-expiry countdown.
(function () {
  const page = document.querySelector("[data-review-page]");
  if (!page) return;

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- Decision choice (Approve / Reject) ----
  const choices = page.querySelectorAll("[data-choice]");
  const panels = page.querySelectorAll("[data-panel]");
  let current = null;

  function choose(kind) {
    current = kind;
    choices.forEach((btn) => {
      const on = btn.dataset.choice === kind;
      btn.setAttribute("aria-checked", on ? "true" : "false");
      btn.classList.toggle("is-selected", on);
      btn.classList.toggle("is-dimmed", kind !== null && !on);
    });
    panels.forEach((panel) => {
      const on = panel.dataset.panel === kind;
      panel.hidden = !on;
      if (on) {
        document.dispatchEvent(new CustomEvent("review:panel-shown", { detail: kind }));
        panel.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
        const focusTarget = kind === "reject" ? panel.querySelector("textarea") : panel.querySelector("[data-ack]");
        focusTarget?.focus({ preventScroll: true });
      }
    });
  }

  choices.forEach((btn) => btn.addEventListener("click", () => {
    choose(current === btn.dataset.choice ? null : btn.dataset.choice);
  }));
  page.querySelectorAll("[data-choice-cancel]").forEach((btn) => btn.addEventListener("click", () => {
    choose(null);
    page.querySelector("[data-choice]")?.focus();
  }));

  // Keyboard: A = approve, R = reject, Esc = back out. Ignored while typing.
  document.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || e.target.isContentEditable) {
      if (e.key === "Escape") e.target.blur();
      return;
    }
    const key = e.key.toLowerCase();
    if (key === "a") { e.preventDefault(); choose("approve"); }
    else if (key === "r") { e.preventDefault(); choose("reject"); }
    else if (e.key === "Escape" && current) { choose(null); }
  });

  // ---- Approve (employee page): checkbox gates the button ----
  const ack = page.querySelector("[data-ack]");
  const approveSubmit = page.querySelector("[data-approve-submit]");
  if (ack && approveSubmit) {
    ack.addEventListener("change", () => { approveSubmit.disabled = !ack.checked; });
  }

  // ---- Reject: quick-reason chips, counter, minimum length ----
  const reason = page.querySelector("#reject-reason");
  const counter = page.querySelector("[data-reason-count]");
  const rejectSubmit = page.querySelector("[data-reject-submit]");
  const chips = page.querySelectorAll("[data-reason-chip]");

  function syncReason() {
    const len = reason.value.trim().length;
    counter.textContent = reason.value.length;
    rejectSubmit.disabled = len < 3;
    chips.forEach((chip) => {
      chip.classList.toggle("is-on", reason.value.includes(chip.textContent.trim()));
    });
  }

  if (reason) {
    reason.addEventListener("input", syncReason);
    chips.forEach((chip) => chip.addEventListener("click", () => {
      const text = chip.textContent.trim();
      if (reason.value.includes(text)) {
        reason.value = reason.value.replace(text, "").replace(/^[\s.,;]+|[\s,;]+$/g, "").replace(/\.\s*\./g, ".");
      } else {
        const base = reason.value.trim();
        reason.value = base ? `${base.replace(/[.\s]*$/, "")}. ${text}. ` : `${text}. `;
      }
      syncReason();
      reason.focus();
      reason.setSelectionRange(reason.value.length, reason.value.length);
    }));
    syncReason();
  }

  // ---- Document preview: hide/show, full screen, loading state ----
  const preview = page.querySelector("[data-doc-preview]");
  if (preview) {
    const body = preview.querySelector("[data-preview-body]");
    const toggle = preview.querySelector("[data-preview-toggle]");
    const full = preview.querySelector("[data-preview-full]");
    const frame = body?.querySelector("iframe, img");

    frame?.addEventListener("load", () => body.classList.add("is-loaded"));
    frame?.addEventListener("error", () => body.classList.add("is-loaded", "is-failed"));

    toggle?.addEventListener("click", () => {
      const open = body.hidden;
      body.hidden = !open;
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.textContent = open ? "Hide preview" : "Show preview";
    });

    full?.addEventListener("click", () => {
      if (body.hidden) toggle?.click();
      if (body.requestFullscreen) body.requestFullscreen();
      else window.open(frame?.src, "_blank", "noopener");
    });
  }

  // ---- Link expiry countdown ----
  const expiry = page.querySelector("[data-expires]");
  if (expiry) {
    const raw = expiry.dataset.expires;
    const at = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(raw) ? raw : raw + "Z");
    const text = expiry.querySelector("[data-expires-text]");

    function tick() {
      const ms = at - Date.now();
      expiry.classList.remove("is-soon", "is-urgent", "is-expired");
      if (ms <= 0) {
        text.textContent = "Link expired. Reload to check.";
        expiry.classList.add("is-expired");
        page.querySelectorAll("[data-choice], [type=submit]").forEach((b) => { b.disabled = true; });
        return false;
      }
      const mins = Math.floor(ms / 60000);
      const days = Math.floor(mins / 1440);
      const hours = Math.floor((mins % 1440) / 60);
      const m = mins % 60;
      let label;
      if (days >= 1) label = `${days} day${days > 1 ? "s" : ""} ${hours} h left`;
      else if (hours >= 1) label = `${hours} h ${m} min left`;
      else label = `${Math.max(m, 1)} min left`;
      text.textContent = `Link expires in ${label.replace(" left", "")}`;
      if (mins < 120) expiry.classList.add("is-urgent");
      else if (mins < 1440) expiry.classList.add("is-soon");
      return true;
    }
    if (tick()) {
      const id = setInterval(() => { if (!tick()) clearInterval(id); }, 30000);
    }
  }
})();
