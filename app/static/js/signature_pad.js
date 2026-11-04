const canvas = document.getElementById("signature-pad");
const ctx = canvas.getContext("2d");
const clearBtn = document.getElementById("clear-signature");
const approveBtn = document.getElementById("approve-btn");
const hiddenInput = document.getElementById("signature-data-url");
const form = document.getElementById("sign-form");

let drawing = false;
let hasInk = false;

function resizeCanvasForDPR() {
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * ratio;
  canvas.height = rect.height * ratio;
  ctx.scale(ratio, ratio);
  ctx.lineWidth = 2;
  ctx.lineCap = "round";
  ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue("--ink").trim() || "#1e2538";
}
resizeCanvasForDPR();

function pointerPos(evt) {
  const rect = canvas.getBoundingClientRect();
  const point = evt.touches ? evt.touches[0] : evt;
  return { x: point.clientX - rect.left, y: point.clientY - rect.top };
}

function startDraw(evt) {
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

clearBtn.addEventListener("click", () => {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  hasInk = false;
  approveBtn.disabled = true;
});

form.addEventListener("submit", (evt) => {
  if (!hasInk) {
    evt.preventDefault();
    return;
  }
  hiddenInput.value = canvas.toDataURL("image/png");
});
