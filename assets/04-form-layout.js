window.addEventListener("DOMContentLoaded", () => {
  if (!window.matchMedia("(max-width: 768px)").matches) {
    return;
  }

  document.querySelectorAll(".lp-form-sidebar[open]").forEach((sidebar) => {
    sidebar.removeAttribute("open");
  });
});
