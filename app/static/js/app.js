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
staggerChildren("table tbody", "tr", 30);
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

// Theme Toggle Button
const themeBtn = document.getElementById('theme-toggle-btn');
if (themeBtn) {
  themeBtn.addEventListener('click', () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
      (!document.documentElement.getAttribute('data-theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
    const nextTheme = isDark ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', nextTheme);
    localStorage.setItem('docuflow-theme', nextTheme);
    if (window.showToast) {
      showToast(nextTheme === 'dark' ? 'Dark theme enabled' : 'Light theme enabled', 'default', 1500);
    }
  });
}

// Topbar Search Clear button
const topbarSearchInput = document.getElementById('topbar-search');
const topbarSearchClear = document.getElementById('topbar-search-clear');
if (topbarSearchInput && topbarSearchClear) {
  const updateClearBtn = () => {
    topbarSearchClear.hidden = !topbarSearchInput.value;
  };
  topbarSearchInput.addEventListener('input', updateClearBtn);
  topbarSearchClear.addEventListener('click', () => {
    topbarSearchInput.value = '';
    updateClearBtn();
    topbarSearchInput.dispatchEvent(new Event('input', { bubbles: true }));
    topbarSearchInput.focus();
  });
  topbarSearchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      topbarSearchInput.value = '';
      updateClearBtn();
      topbarSearchInput.dispatchEvent(new Event('input', { bubbles: true }));
      topbarSearchInput.blur();
    }
  });
}

// Donut Chart & Legend Synchronized Hovering
document.querySelectorAll('.donut-row').forEach((wrap) => {
  const circles = Array.from(wrap.querySelectorAll('svg circle[stroke-dasharray]'));
  const legendItems = Array.from(wrap.querySelectorAll('.donut-legend li'));
  if (circles.length && circles.length === legendItems.length) {
    circles.forEach((circle, i) => {
      circle.addEventListener('mouseenter', () => {
        circles.forEach((c, idx) => c.style.opacity = idx === i ? '1' : '0.4');
        legendItems.forEach((li, idx) => li.classList.toggle('is-highlighted', idx === i));
      });
      circle.addEventListener('mouseleave', () => {
        circles.forEach((c) => c.style.opacity = '1');
        legendItems.forEach((li) => li.classList.remove('is-highlighted'));
      });
    });
    legendItems.forEach((item, i) => {
      item.addEventListener('mouseenter', () => {
        circles.forEach((c, idx) => {
          c.style.opacity = idx === i ? '1' : '0.4';
          if (idx === i) c.style.strokeWidth = '20';
        });
        item.classList.add('is-highlighted');
      });
      item.addEventListener('mouseleave', () => {
        circles.forEach((c) => {
          c.style.opacity = '1';
          c.style.strokeWidth = '16';
        });
        item.classList.remove('is-highlighted');
      });
    });
  }
});

// Progress bar animation on load
document.querySelectorAll("[data-progress-fill]").forEach((el) => {
  const target = parseInt(el.dataset.target, 10) || 0;
  requestAnimationFrame(() => {
    el.style.width = `${target}%`;
  });
});

// Spotlight Command Palette
(function() {
  const palette = document.getElementById("command-palette");
  const input = document.getElementById("cmd-input");
  const results = document.getElementById("cmd-results");
  if (!palette || !input || !results) return;

  const defaultCommands = [
    { group: "Navigation", label: "Dashboard", desc: "View document stats & active routing", icon: "grid", href: "/" },
    { group: "Navigation", label: "Documents Library", desc: "Browse and download uploaded files", icon: "folder", href: "/documents" },
    { group: "Navigation", label: "Route New Document", desc: "Start a new review and signing chain", icon: "plus", href: "/chains/new" },
    { group: "Navigation", label: "Settings", desc: "Manage profile, appearance, and alerts", icon: "settings", href: "/settings" },
    { group: "Actions", label: "Toggle Dark / Light Theme", desc: "Switch appearance mode instantly", icon: "sun", action: () => document.getElementById("theme-toggle-btn")?.click() },
    { group: "Actions", label: "Filter: In Progress", desc: "Show only documents currently in review", icon: "clock", action: () => {
      const card = document.querySelector('.stat-card-v2.tone-progress');
      if (card) card.click();
      else window.location.href = "/";
    }},
    { group: "Actions", label: "Filter: Approved Documents", desc: "Show completed & approved documents", icon: "check", action: () => {
      const card = document.querySelector('.stat-card-v2.tone-approved');
      if (card) card.click();
      else window.location.href = "/";
    }},
    { group: "Actions", label: "Filter: Rejected Documents", desc: "Show rejected review chains", icon: "x", action: () => {
      const card = document.querySelector('.stat-card-v2.tone-rejected');
      if (card) card.click();
    }},
    { group: "Actions", label: "Show All Documents", desc: "Reset active document filters", icon: "refresh", action: () => {
      const card = document.querySelector('.stat-card-v2.tone-total');
      if (card) card.click();
    }}
  ];

  function getDocumentCommands() {
    const docs = [];
    document.querySelectorAll("tr[data-href]").forEach((tr) => {
      const title = tr.querySelector(".doc-title-text, strong, td:first-child")?.textContent.trim() || "";
      const href = tr.dataset.href;
      const status = tr.dataset.status || "";
      if (title && href) {
        docs.push({ group: "Documents", label: title, desc: status.replace("_", " ") || "Routed document", icon: "file", href });
      }
    });
    return docs;
  }

  let selectedIndex = 0;
  let currentList = [];

  function getIconSvg(icon) {
    if (icon === "grid") return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/></svg>';
    if (icon === "folder") return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>';
    if (icon === "plus") return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>';
    if (icon === "settings") return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>';
    if (icon === "sun") return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>';
    if (icon === "clock") return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>';
    if (icon === "check") return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>';
    if (icon === "x") return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    if (icon === "file") return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>';
    return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>';
  }

  function renderList(query = "") {
    const q = query.trim().toLowerCase();
    const all = [...defaultCommands, ...getDocumentCommands()];
    const filtered = q ? all.filter(c => c.label.toLowerCase().includes(q) || c.desc.toLowerCase().includes(q)) : all;
    currentList = filtered;
    selectedIndex = Math.min(selectedIndex, Math.max(0, filtered.length - 1));

    results.innerHTML = "";
    if (filtered.length === 0) {
      results.innerHTML = '<div style="padding: 1.5rem; text-align: center; color: var(--ink-faint); font-size: 0.9rem;">No matching commands or documents found</div>';
      return;
    }

    let lastGroup = "";
    filtered.forEach((item, idx) => {
      if (item.group !== lastGroup) {
        lastGroup = item.group;
        const groupEl = document.createElement("div");
        groupEl.className = "cmd-group-label";
        groupEl.textContent = lastGroup;
        results.appendChild(groupEl);
      }
      const itemEl = document.createElement("div");
      itemEl.className = `cmd-item${idx === selectedIndex ? " is-selected" : ""}`;
      itemEl.innerHTML = `
        <span class="cmd-item-icon">${getIconSvg(item.icon)}</span>
        <div class="cmd-item-text">
          <span class="cmd-item-title">${item.label}</span>
          <span class="cmd-item-desc">${item.desc}</span>
        </div>
      `;
      itemEl.addEventListener("click", () => executeItem(item));
      itemEl.addEventListener("mouseenter", () => {
        selectedIndex = idx;
        updateSelection();
      });
      results.appendChild(itemEl);
    });
  }

  function updateSelection() {
    const items = results.querySelectorAll(".cmd-item");
    items.forEach((el, idx) => el.classList.toggle("is-selected", idx === selectedIndex));
    items[selectedIndex]?.scrollIntoView({ block: "nearest" });
  }

  function executeItem(item) {
    closePalette();
    if (item.action) {
      item.action();
    } else if (item.href) {
      window.location.href = item.href;
    }
  }

  function openPalette() {
    palette.hidden = false;
    input.value = "";
    renderList();
    setTimeout(() => input.focus(), 50);
  }

  function closePalette() {
    palette.hidden = true;
  }

  palette.addEventListener("click", (e) => {
    if (e.target === palette) closePalette();
  });

  input.addEventListener("input", () => {
    selectedIndex = 0;
    renderList(input.value);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closePalette();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (currentList.length) {
        selectedIndex = (selectedIndex + 1) % currentList.length;
        updateSelection();
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (currentList.length) {
        selectedIndex = (selectedIndex - 1 + currentList.length) % currentList.length;
        updateSelection();
      }
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (currentList[selectedIndex]) {
        executeItem(currentList[selectedIndex]);
      }
    }
  });

  // Open on Ctrl+K or Cmd+K
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (palette.hidden) openPalette();
      else closePalette();
    }
  });

  // On pages with no document table to search inline, the topbar search box
  // just opens the full command palette instead.
  const topSearch = document.getElementById("topbar-search");
  topSearch?.addEventListener("focus", (e) => {
    if (!document.getElementById("chain-table")) {
      e.preventDefault();
      topSearch.blur();
      openPalette();
    }
  });
})();

// Topbar instant document search (dashboard): live-filters routed documents
// into a dropdown as you type, with keyboard navigation and match highlighting.
(function () {
  const input = document.getElementById("topbar-search");
  const wrap = input?.closest("[data-topbar-search]");
  const panel = document.getElementById("topbar-search-results");
  const table = document.getElementById("chain-table");
  if (!input || !wrap || !panel || !table) return;

  const STATUS_LABEL = { PENDING: "Pending", IN_PROGRESS: "In Progress", APPROVED: "Approved", REJECTED: "Rejected" };
  const fileIcon = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>';

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function highlight(text, q) {
    const safe = escapeHtml(text);
    if (!q) return safe;
    const idx = safe.toLowerCase().indexOf(q.toLowerCase());
    if (idx === -1) return safe;
    return safe.slice(0, idx) + "<mark>" + safe.slice(idx, idx + q.length) + "</mark>" + safe.slice(idx + q.length);
  }

  function getDocs() {
    return Array.from(table.querySelectorAll("tbody tr[data-href]")).map((tr) => ({
      title: tr.querySelector(".doc-title-text")?.textContent.trim() || tr.dataset.filename,
      filename: tr.querySelector(".doc-filename")?.textContent.trim() || "",
      status: tr.dataset.status,
      href: tr.dataset.href,
    }));
  }

  let matches = [];
  let activeIndex = -1;

  function setActive(idx) {
    activeIndex = idx;
    panel.querySelectorAll(".topbar-search-item").forEach((el, i) => el.classList.toggle("is-active", i === idx));
    panel.querySelector(".topbar-search-item.is-active")?.scrollIntoView({ block: "nearest" });
  }

  function open() {
    panel.hidden = false;
    wrap.setAttribute("data-open", "true");
    input.setAttribute("aria-expanded", "true");
  }
  function close() {
    panel.hidden = true;
    wrap.removeAttribute("data-open");
    input.setAttribute("aria-expanded", "false");
    matches = [];
    activeIndex = -1;
  }

  function render(query) {
    const q = query.trim();
    if (!q) { close(); return; }

    const docs = getDocs();
    matches = docs.filter((d) => (d.title + " " + d.filename).toLowerCase().includes(q.toLowerCase())).slice(0, 7);

    let html = `<div class="topbar-search-label">${docs.length ? "Documents" : "No routed documents yet"}</div>`;
    if (matches.length) {
      html += matches.map((d) => `
        <a href="${d.href}" class="topbar-search-item" role="option">
          <span class="topbar-search-item-icon">${fileIcon}</span>
          <span class="topbar-search-item-text">
            <span class="topbar-search-item-title">${highlight(d.title, q)}</span>
            <span class="topbar-search-item-desc">${highlight(d.filename, q)}</span>
          </span>
          <span class="stamp stamp-${d.status}">${STATUS_LABEL[d.status] || d.status}</span>
        </a>
      `).join("");
      html += `<div class="topbar-search-footer"><span><kbd>&uarr;</kbd><kbd>&darr;</kbd> navigate</span><span><kbd>&crarr;</kbd> open</span></div>`;
    } else if (docs.length) {
      html += `<div class="topbar-search-empty">No documents match &ldquo;${escapeHtml(q)}&rdquo;</div>`;
    }
    panel.innerHTML = html;
    setActive(matches.length ? 0 : -1);
    open();
  }

  input.addEventListener("input", () => render(input.value));
  input.addEventListener("focus", () => { if (input.value.trim()) render(input.value); });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      close();
    } else if (e.key === "ArrowDown" && matches.length) {
      e.preventDefault();
      setActive((activeIndex + 1) % matches.length);
    } else if (e.key === "ArrowUp" && matches.length) {
      e.preventDefault();
      setActive((activeIndex - 1 + matches.length) % matches.length);
    } else if (e.key === "Enter" && activeIndex >= 0 && matches[activeIndex]) {
      e.preventDefault();
      window.location.href = matches[activeIndex].href;
    }
  });

  panel.addEventListener("mousemove", (e) => {
    const item = e.target.closest(".topbar-search-item");
    if (!item) return;
    const idx = Array.from(panel.querySelectorAll(".topbar-search-item")).indexOf(item);
    if (idx !== activeIndex) setActive(idx);
  });

  document.addEventListener("click", (e) => {
    if (!wrap.contains(e.target)) close();
  });
})();

// Advanced Donut & Trend Chart Interactivity
document.querySelectorAll('.dash-charts-row').forEach((row) => {
  const segments = Array.from(row.querySelectorAll('.donut-segment'));
  const legendItems = Array.from(row.querySelectorAll('.donut-legend-item'));

  function highlightSegment(idx) {
    segments.forEach((seg) => {
      const match = seg.dataset.segmentIdx === String(idx);
      seg.style.opacity = match ? '1' : '0.3';
      seg.classList.toggle('is-active', match);
    });
    legendItems.forEach((li) => {
      li.classList.toggle('is-highlighted', li.dataset.segmentIdx === String(idx));
    });
  }

  function resetHighlight() {
    segments.forEach((seg) => {
      seg.style.opacity = '1';
      seg.classList.remove('is-active');
    });
    legendItems.forEach((li) => li.classList.remove('is-highlighted'));
  }

  segments.forEach((seg) => {
    seg.addEventListener('mouseenter', () => highlightSegment(seg.dataset.segmentIdx));
    seg.addEventListener('mouseleave', resetHighlight);
  });

  legendItems.forEach((li) => {
    li.addEventListener('mouseenter', () => highlightSegment(li.dataset.segmentIdx));
    li.addEventListener('mouseleave', resetHighlight);
  });
});
