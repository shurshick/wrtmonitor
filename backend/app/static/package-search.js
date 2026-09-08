(() => {
  document.documentElement.dataset.packageSearchReady = "true";
  document.addEventListener("input", (event) => {
    const input = event.target.closest("[data-package-search]");
    if (!input) return;
    const list = input.closest("details")?.querySelector("[data-package-list]");
    if (!list) return;
    const rows = [...list.querySelectorAll("[data-package-name]")];
    const empty = list.querySelector("[data-package-empty]");
    const query = input.value.trim().toLocaleLowerCase();
    let visible = 0;
    rows.forEach((row) => {
      const matches = !query || row.dataset.packageName.includes(query);
      row.hidden = !matches;
      if (matches) visible += 1;
    });
    if (empty) empty.hidden = visible !== 0;
  });
})();
