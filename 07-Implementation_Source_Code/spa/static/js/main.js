// Upload dropzone: drag & drop + selected-file feedback.
// No external dependencies; progressive enhancement only —
// the form works fine via plain click-to-browse if JS is disabled.
(function () {
  const dropzone = document.getElementById("dropzone");
  const input = document.getElementById("raw_file");
  const label = document.getElementById("file-chosen");
  if (!dropzone || !input) return;

  const defaultText = label ? label.textContent : "";

  function showFileName(file) {
    if (!label || !file) return;
    const sizeKb = (file.size / 1024).toFixed(0);
    label.textContent = `${file.name} · ${sizeKb} KB`;
  }

  input.addEventListener("change", () => {
    if (input.files && input.files[0]) showFileName(input.files[0]);
    else if (label) label.textContent = defaultText;
  });

  ["dragenter", "dragover"].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const files = e.dataTransfer && e.dataTransfer.files;
    if (files && files.length) {
      input.files = files;
      showFileName(files[0]);
    }
  });
})();
