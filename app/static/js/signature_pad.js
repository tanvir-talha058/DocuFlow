const canvas = document.getElementById("signature-pad");
const ctx = canvas.getContext("2d");
const clearBtn = document.getElementById("clear-signature");
const undoBtn = document.getElementById("undo-signature");
const approveBtn = document.getElementById("approve-btn");
const hiddenInput = document.getElementById("signature-data-url");
const form = document.getElementById("sign-form");

const tabDraw = document.querySelector('[data-sign-tab="draw"]');
const tabType = document.querySelector('[data-sign-tab="type"]');
const panelDraw = document.getElementById("panel-draw");
const panelType = document.getElementById("panel-type");
const typedNameInput = document.getElementById("typed-name");
const typedPreview = document.getElementById("typed-preview");

let currentMode = "draw"; // "draw" or "type"
let currentColor = "#1e3a8a";
let currentWidth = 2.5;
let drawing = false;
let hasInk = false;
let strokeHistory = [];

function resizeCanvasForDPR() {
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * ratio;
  canvas.height = rect.height * ratio;
  ctx.scale(ratio, ratio);
  ctx.lineWidth = currentWidth;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = currentColor;
}
resizeCanvasForDPR();

function saveSnapshot() {
  strokeHistory.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
  if (strokeHistory.length > 25) strokeHistory.shift();
}

function pointerPos(evt) {
  const rect = canvas.getBoundingClientRect();
  const point = evt.touches ? evt.touches[0] : evt;
  return { x: point.clientX - rect.left, y: point.clientY - rect.top };
}

function startDraw(evt) {
  saveSnapshot();
  drawing = true;
  hasInk = true;
  const { x, y } = pointerPos(evt);
  ctx.beginPath();
  ctx.moveTo(x, y);
  approveBtn.disabled = false;
  evt.preventDefault();
}

function moveDraw(evt) {
  if (!drawing) return;
  const { x, y } = pointerPos(evt);
  ctx.lineTo(x, y);
  ctx.stroke();
  evt.preventDefault();
}

function endDraw() {
  drawing = false;
}

canvas.addEventListener("mousedown", startDraw);
canvas.addEventListener("mousemove", moveDraw);
canvas.addEventListener("mouseup", endDraw);
canvas.addEventListener("mouseleave", endDraw);
canvas.addEventListener("touchstart", startDraw);
canvas.addEventListener("touchmove", moveDraw);
canvas.addEventListener("touchend", endDraw);

clearBtn?.addEventListener("click", () => {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  strokeHistory = [];
  hasInk = false;
  approveBtn.disabled = true;
});

undoBtn?.addEventListener("click", () => {
  if (strokeHistory.length > 0) {
    const previous = strokeHistory.pop();
    ctx.putImageData(previous, 0, 0);
    hasInk = strokeHistory.length > 0;
    approveBtn.disabled = !hasInk;
  }
});

// Color Picker
document.querySelectorAll(".color-dot").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".color-dot").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    currentColor = btn.dataset.color;
    ctx.strokeStyle = currentColor;
  });
});

// Width Picker
document.querySelectorAll(".width-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".width-btn").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    currentWidth = parseFloat(btn.dataset.width);
    ctx.lineWidth = currentWidth;
  });
});

// Render typed signature to canvas
function renderTypedToCanvas(text) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!text.trim()) {
    hasInk = false;
    approveBtn.disabled = true;
    return;
  }
  const ratio = window.devicePixelRatio || 1;
  const w = canvas.width / ratio;
  const h = canvas.height / ratio;

  ctx.save();
  ctx.font = "600 44px 'Caveat', cursive, Georgia";
  ctx.fillStyle = currentColor;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, w / 2, h / 2 + 5);
  ctx.restore();

  hasInk = true;
  approveBtn.disabled = false;
}

// Tabs
tabDraw?.addEventListener("click", () => {
  currentMode = "draw";
  tabDraw.classList.add("is-active");
  tabType.classList.remove("is-active");
  panelDraw.hidden = false;
  panelType.hidden = true;
  approveBtn.disabled = !hasInk;
});

tabType?.addEventListener("click", () => {
  currentMode = "type";
  tabType.classList.add("is-active");
  tabDraw.classList.remove("is-active");
  panelType.hidden = false;
  panelDraw.hidden = true;
  renderTypedToCanvas(typedNameInput.value);
});

typedNameInput?.addEventListener("input", () => {
  const val = typedNameInput.value;
  typedPreview.textContent = val || "Your Signature";
  if (currentMode === "type") {
    renderTypedToCanvas(val);
  }
});

form.addEventListener("submit", (evt) => {
  if (currentMode === "type") {
    renderTypedToCanvas(typedNameInput.value);
  }
  if (!hasInk) {
    evt.preventDefault();
    return;
  }
  hiddenInput.value = canvas.toDataURL("image/png");
});
