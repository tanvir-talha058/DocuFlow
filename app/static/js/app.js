// Shared interactivity: toasts, button loading states, staggered reveals, copy-to-clipboard.

function ensureToastStack() {
  let stack = document.querySelector(".toast-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.className = "toast-stack";
    document.body.appendChild(stack);
  }
  return stack;
}

function showToast(message, variant = "default", duration = 3200) {
  const stack = ensureToastStack();
  const toast = document.createElement("div");
  toast.className = `toast${variant === "success" ? " toast-success" : ""}${variant === "error" ? " toast-error" : ""}`;
  toast.textContent = message;
  stack.appendChild(toast);
  setTimeout(() => {
    toast.classList.add("is-leaving");
    toast.addEventListener("animationend", () => toast.remove(), { once: true });
  }, duration);
}
window.showToast = showToast;

// Put a spinner on the submit button and keep it disabled while a form is in flight.
document.addEventListener("submit", (event) => {
  const form = event.target;
  if (event.defaultPrevented || !(form instanceof HTMLFormElement) || form.dataset.noLoading) return;
  const submitBtn = form.querySelector('button[type="submit"]');
  if (submitBtn && !submitBtn.disabled) {
    submitBtn.classList.add("is-loading");
    submitBtn.disabled = true;
  }
});

// Stagger entrance animation for list-like groups so items cascade in rather than popping together.
function staggerChildren(selector, itemSelector, stepMs = 40) {
  document.querySelectorAll(selector).forEach((container) => {
    Array.from(container.querySelectorAll(itemSelector)).forEach((el, i) => {
      el.style.animationDelay = `${i * stepMs}ms`;
    });
  });
}
staggerChildren(".routing-list", ".routing-row", 60);
staggerChildren(".ledger", "li", 35);
staggerChildren("table tbody", "tr", 30);
staggerChildren(".stat-row", ".stat-card", 50);
staggerChildren(".activity-timeline", ".activity-row", 50);
staggerChildren(".stat-grid-v2", ".stat-card-v2", 60);
staggerChildren(".feed", ".feed-row", 45);
staggerChildren(".donut-legend", "li", 60);
staggerChildren("#waiting-on-you", ".waiting-row", 50);

// Copy-to-clipboard buttons: <button class="btn-copy" data-copy="text-to-copy">Copy</button>
document.querySelectorAll(".btn-copy").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const text = btn.dataset.copy || "";
    try {
      await navigator.clipboard.writeText(text);
    } catch (err) {
      showToast("Couldn't copy to clipboard", "error");
      return;
    }
    const original = btn.textContent;
    btn.classList.add("is-copied");
    btn.textContent = "Copied";
    showToast("Copied to clipboard", "success", 1800);
    setTimeout(() => {
      btn.classList.remove("is-copied");
      btn.textContent = original;
    }, 1600);
  });
});

// Count up to a number on load: <span class="stat-value" data-count-to="12">12</span>
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
document.querySelectorAll("[data-count-to]").forEach((el) => {
  const target = parseInt(el.dataset.countTo, 10);
  if (!Number.isFinite(target) || prefersReducedMotion) return;
  const duration = 700;
  const start = performance.now();
  function tick(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(target * eased);
    if (progress < 1) requestAnimationFrame(tick);
    else el.textContent = target;
  }
  el.textContent = "0";
  requestAnimationFrame(tick);
});

// Generic dropdown: <div class="dropdown" data-dropdown><button data-dropdown-trigger>...<div class="dropdown-panel">
document.querySelectorAll("[data-dropdown]").forEach((dropdown) => {
  const trigger = dropdown.querySelector("[data-dropdown-trigger]");
  if (!trigger) return;
  trigger.addEventListener("click", (event) => {
    event.stopPropagation();
    const isOpen = dropdown.classList.contains("is-open");
    document.querySelectorAll("[data-dropdown].is-open").forEach((d) => {
      d.classList.remove("is-open");
      d.querySelector("[data-dropdown-trigger]")?.setAttribute("aria-expanded", "false");
    });
    if (!isOpen) {
      dropdown.classList.add("is-open");
      trigger.setAttribute("aria-expanded", "true");
    }
  });
});
document.addEventListener("click", () => {
  document.querySelectorAll("[data-dropdown].is-open").forEach((d) => {
    d.classList.remove("is-open");
    d.querySelector("[data-dropdown-trigger]")?.setAttribute("aria-expanded", "false");
  });
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.querySelectorAll("[data-dropdown].is-open").forEach((d) => d.classList.remove("is-open"));
  }
});

// Draw the trend line in from left to right on load, then fade the area fill in under it.
document.querySelectorAll("[data-trend-line]").forEach((line) => {
  const length = line.getTotalLength();
  line.style.strokeDasharray = `${length}`;
  line.style.strokeDashoffset = `${length}`;
  requestAnimationFrame(() => {
    line.style.transition = "stroke-dashoffset 0.9s cubic-bezier(.22,1,.36,1)";
    line.style.strokeDashoffset = "0";
  });
  const area = line.parentElement?.querySelector("[data-trend-area]");
  if (area) {
    area.style.opacity = "0";
    area.style.transition = "opacity 0.6s ease 0.5s";
    requestAnimationFrame(() => { area.style.opacity = "1"; });
  }
});

// Trend chart crosshair + tooltip: track the nearest point to the cursor.
document.querySelectorAll("[data-trend-wrap]").forEach((wrap) => {
  const svg = wrap.querySelector(".trend-chart");
  const crosshair = wrap.querySelector("[data-trend-crosshair]");
  const tooltip = wrap.querySelector("[data-trend-tooltip]");
  const tooltipLabel = tooltip?.querySelector("[data-trend-tooltip-label]");
  const tooltipValue = tooltip?.querySelector("[data-trend-tooltip-value]");
  const hits = Array.from(wrap.querySelectorAll("[data-trend-hit]"));
  if (!svg || !crosshair || !tooltip || hits.length === 0) return;

  const viewBox = svg.viewBox.baseVal;

  const dots = wrap.querySelectorAll("[data-trend-dot]");

  function showPoint(hit) {
    const svgRect = svg.getBoundingClientRect();
    const scaleX = svgRect.width / viewBox.width;
    const x = parseFloat(hit.dataset.x);
    crosshair.setAttribute("x1", x);
    crosshair.setAttribute("x2", x);
    crosshair.hidden = false;

    dots.forEach((dot) => dot.classList.remove("is-active"));
    hit.previousElementSibling?.classList.add("is-active");

    tooltipLabel.textContent = hit.dataset.label;
    const value = hit.dataset.value;
    tooltipValue.textContent = `${value} document${value === "1" ? "" : "s"}`;
    tooltip.hidden = false;

    const pixelX = x * scaleX;
    const wrapWidth = wrap.getBoundingClientRect().width;
    tooltip.style.left = `${Math.min(Math.max(pixelX, 40), wrapWidth - 40)}px`;
  }

  hits.forEach((hit) => {
    hit.addEventListener("mouseenter", () => showPoint(hit));
    hit.addEventListener("focus", () => showPoint(hit));
  });
  wrap.addEventListener("mouseleave", () => {
    crosshair.hidden = true;
    tooltip.hidden = true;
    dots.forEach((dot) => dot.classList.remove("is-active"));
  });
});

// Ctrl/Cmd+K focuses the topbar search, like most app search bars.
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    const search = document.getElementById("topbar-search");
    if (search) {
      event.preventDefault();
      search.focus();
      search.select();
    }
  }
});

// Relative time text: <span data-timeago="2026-11-04T09:14:00">Nov 4, 9:14 AM</span>
document.querySelectorAll("[data-timeago]").forEach((el) => {
  const then = new Date(el.dataset.timeago + "Z");
  if (Number.isNaN(then.getTime())) return;
  const diffSeconds = Math.max(0, (Date.now() - then.getTime()) / 1000);
  const units = [
    [60, "s"], [60, "m"], [24, "h"], [7, "d"], [4.345, "w"], [12, "mo"], [Infinity, "y"],
  ];
  let value = diffSeconds;
  let label = "s";
  for (const [size, unitLabel] of units) {
    if (value < size) { label = unitLabel; break; }
    value /= size;
    label = unitLabel;
  }
  el.textContent = value < 1 ? "just now" : `${Math.floor(value)}${label} ago`;
});

// Click-anywhere-on-row navigation for rows marked data-href.
document.querySelectorAll("tr[data-href]").forEach((row) => {
  row.addEventListener("click", (event) => {
    if (event.target.closest("a, button")) return;
    window.location.href = row.dataset.href;
  });
});
// Enhanced interactions
document.addEventListener('DOMContentLoaded', function() {
  // Add ripple effect to buttons
  document.querySelectorAll('.btn:not(.btn-copy)').forEach(btn => {
    btn.addEventListener('click', function(e) {
      const ripple = document.createElement('span');
      const rect = btn.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      const x = e.clientX - rect.left - size / 2;
      const y = e.clientY - rect.top - size / 2;
      
      ripple.style.cssText = `position: absolute; width: ${size}px; height: ${size}px; left: ${x}px; top: ${y}px; background: rgba(255,255,255,0.5); border-radius: 50%; transform: scale(0); animation: ripple 0.6s ease-out; pointer-events: none;`;
      btn.style.position = 'relative';
      btn.style.overflow = 'hidden';
      btn.appendChild(ripple);
      setTimeout(() => ripple.remove(), 600);
    });
  });
});

// Add ripple animation
const style = document.createElement('style');
style.textContent = '@keyframes ripple { to { transform: scale(4); opacity: 0; } }';
document.head.appendChild(style);
