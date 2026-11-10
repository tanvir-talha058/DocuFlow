const rowsContainer = document.getElementById("approver-rows");
const rowTemplate = document.getElementById("approver-row-template");
const fileInput = document.getElementById("file");
const submitBtn = document.getElementById("submit-chain");
const submitHint = document.getElementById("submit-hint");

const messageInput = document.getElementById("message");
const messageCounter = document.getElementById("message-counter");
if (messageInput && messageCounter) {
  messageInput.addEventListener("input", () => {
    messageCounter.textContent = messageInput.value.length;
  });
}

function renumberRows() {
  Array.from(rowsContainer.children).forEach((row, i) => {
    const badge = row.querySelector("[data-row-index]");
    if (badge) badge.textContent = i + 1;
  });
}

function rowIsFilled(row) {
  const type = row.querySelector(".approver-type").value;
  if (type === "CUSTOMER") {
    const name = row.querySelector(".customer-name").value.trim();
    const email = row.querySelector(".customer-email").value.trim();
    return Boolean(name && email);
  }
  const hiddenId = row.querySelector(".approver-employee-id").value;
  return Boolean(hiddenId);
}

function validateForm() {
  const hasFile = fileInput.files && fileInput.files.length > 0;
  const rows = Array.from(rowsContainer.children);
  const allFilled = rows.length > 0 && rows.every(rowIsFilled);
  submitBtn.disabled = !(hasFile && allFilled);

  if (!submitHint) return;
  if (hasFile && allFilled) {
    submitHint.hidden = true;
  } else if (!hasFile && !allFilled) {
    submitHint.textContent = "Choose a file and pick at least one approver from the suggestions to continue.";
    submitHint.hidden = false;
  } else if (!hasFile) {
    submitHint.textContent = "Choose a file to continue.";
    submitHint.hidden = false;
  } else {
    submitHint.textContent = "Pick at least one approver from the suggestions to continue.";
    submitHint.hidden = false;
  }
}

const dropzone = document.getElementById("dropzone");
const dropzoneText = document.getElementById("dropzone-text");
const dropzoneFilename = document.getElementById("dropzone-filename");

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function updateDropzone() {
  const file = fileInput.files && fileInput.files[0];
  if (file) {
    dropzone.classList.add("has-file");
    dropzoneText.hidden = true;
    dropzoneFilename.hidden = false;
    const ext = (file.name.split(".").pop() || "FILE").toUpperCase();
    dropzoneFilename.innerHTML = `
      <div class="dropzone-file-pill">
        <span class="file-ext-badge">${ext}</span>
        <span class="file-name-text">${file.name}</span>
        <span class="file-size-text">(${formatBytes(file.size)})</span>
        <span class="file-change-hint">Click or drop to replace</span>
      </div>
    `;
  } else {
    dropzone.classList.remove("has-file");
    dropzoneText.hidden = false;
    dropzoneFilename.hidden = true;
    dropzoneFilename.innerHTML = "";
  }
}

fileInput.addEventListener("change", () => {
  updateDropzone();
  validateForm();
});

["dragenter", "dragover"].forEach((evt) =>
  fileInput.addEventListener(evt, () => dropzone.classList.add("is-dragover"))
);
["dragleave", "drop"].forEach((evt) =>
  fileInput.addEventListener(evt, () => dropzone.classList.remove("is-dragover"))
);

function wireRow(row) {
  const typeSelect = row.querySelector(".approver-type");
  const employeeWrap = row.querySelector(".employee-input");
  const customerWraps = row.querySelectorAll(".customer-input");
  const search = row.querySelector(".approver-search");
  const hiddenId = row.querySelector(".approver-employee-id");
  const removeBtn = row.querySelector(".approver-remove");
  const customerName = row.querySelector(".customer-name");
  const customerEmail = row.querySelector(".customer-email");

  const list = document.createElement("div");
  list.className = "approver-suggestions";
  list.hidden = true;
  employeeWrap.appendChild(list);
  let highlighted = -1;

  function renderSuggestions(employees) {
    list.innerHTML = "";
    highlighted = -1;
    if (!employees.length) {
      list.hidden = true;
      return;
    }
    list.hidden = false;
    employees.forEach((emp) => {
      const item = document.createElement("div");
      item.className = "suggestion-item";
      const initials = (emp.display_name || "?")
        .split(" ")
        .filter(Boolean)
        .slice(0, 2)
        .map(p => p[0].toUpperCase())
        .join("");
      item.innerHTML = `
        <span class="suggestion-avatar">${initials}</span>
        <div class="suggestion-details">
          <strong class="suggestion-name">${emp.display_name}</strong>
          <span class="suggestion-email">${emp.email}</span>
        </div>
      `;
      item.addEventListener("mousedown", (e) => {
        e.preventDefault();
        search.value = `${emp.display_name} (${emp.email})`;
        hiddenId.value = emp.id;
        list.hidden = true;
        validateForm();
      });
      list.appendChild(item);
    });
  }

  typeSelect.addEventListener("change", () => {
    const isCustomer = typeSelect.value === "CUSTOMER";
    employeeWrap.hidden = isCustomer;
    customerWraps.forEach((w) => (w.hidden = !isCustomer));
    validateForm();
  });

  let debounceTimer;
  search.addEventListener("input", () => {
    hiddenId.value = "";
    const q = search.value.trim();
    clearTimeout(debounceTimer);
    if (q.length < 1) {
      list.hidden = true;
      validateForm();
      return;
    }
    debounceTimer = setTimeout(async () => {
      const resp = await fetch(`/api/employees/search?q=${encodeURIComponent(q)}`);
      if (!resp.ok) return;
      renderSuggestions(await resp.json());
    }, 150);
    validateForm();
  });

  search.addEventListener("keydown", (e) => {
    const items = Array.from(list.children);
    if (list.hidden || !items.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      highlighted = Math.min(highlighted + 1, items.length - 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      highlighted = Math.max(highlighted - 1, 0);
    } else if (e.key === "Enter" && highlighted >= 0) {
      e.preventDefault();
      items[highlighted].dispatchEvent(new MouseEvent("mousedown"));
      return;
    } else if (e.key === "Escape") {
      list.hidden = true;
      return;
    } else {
      return;
    }
    items.forEach((item, i) => item.classList.toggle("is-highlighted", i === highlighted));
  });

  search.addEventListener("blur", () => setTimeout(() => (list.hidden = true), 100));

  customerName.addEventListener("input", validateForm);
  customerEmail.addEventListener("input", validateForm);

  removeBtn.addEventListener("click", () => {
    if (rowsContainer.children.length <= 1) return;
    row.classList.add("is-removing");
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      row.remove();
      renumberRows();
      validateForm();
    };
    row.addEventListener("transitionend", finish, { once: true });
    setTimeout(finish, 250);
  });

  row.addEventListener("dragstart", (e) => {
    row.classList.add("is-dragging");
    e.dataTransfer.effectAllowed = "move";
  });
  row.addEventListener("dragend", () => row.classList.remove("is-dragging"));

  row.addEventListener("dragover", (e) => {
    e.preventDefault();
    const dragging = rowsContainer.querySelector(".is-dragging");
    if (!dragging || dragging === row) return;
    const rect = row.getBoundingClientRect();
    const before = e.clientY < rect.top + rect.height / 2;
    rowsContainer.insertBefore(dragging, before ? row : row.nextSibling);
    renumberRows();
  });
}

function addRow() {
  const fragment = rowTemplate.content.cloneNode(true);
  const row = fragment.querySelector("[data-row]");
  rowsContainer.appendChild(row);
  wireRow(row);
  renumberRows();
  validateForm();
}

document.getElementById("add-approver").addEventListener("click", addRow);

addRow();
// Enhanced dropzone
document.addEventListener('DOMContentLoaded', function() {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file');
  const dropzoneText = document.getElementById('dropzone-text');
  const dropzoneFilename = document.getElementById('dropzone-filename');
  
  if (dropzone && fileInput) {
    dropzone.addEventListener('click', () => fileInput.click());
    
    fileInput.addEventListener('change', function() {
      if (this.files.length > 0) {
        dropzone.classList.add('has-file');
        const fileName = this.files[0].name;
        dropzoneText.style.display = 'none';
        dropzoneFilename.textContent = fileName;
        dropzoneFilename.hidden = false;
      } else {
        dropzone.classList.remove('has-file');
        dropzoneText.style.display = 'block';
        dropzoneFilename.hidden = true;
      }
    });
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      dropzone.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
      e.preventDefault();
      e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
      dropzone.addEventListener(eventName, () => dropzone.classList.add('is-dragover'), false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
      dropzone.addEventListener(eventName, () => dropzone.classList.remove('is-dragover'), false);
    });
    
    dropzone.addEventListener('drop', function(e) {
      const dt = e.dataTransfer;
      const files = dt.files;
      fileInput.files = files;
      const event = new Event('change', { bubbles: true });
      fileInput.dispatchEvent(event);
    });
  }
  
  // Message counter
  const messageInput = document.getElementById('message');
  const messageCounter = document.getElementById('message-counter');
  if (messageInput && messageCounter) {
    messageInput.addEventListener('input', function() {
      messageCounter.textContent = this.value.length;
    });
  }
});
