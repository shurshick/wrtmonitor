(() => {
  const input = document.querySelector("[data-package-search]");
  const list = document.querySelector("[data-package-list]");
  if (!input || !list) return;

  const rows = [...list.querySelectorAll("[data-package-name]")];
  const empty = list.querySelector("[data-package-empty]");
  const filter = () => {
    const query = input.value.trim().toLocaleLowerCase();
    let visible = 0;
    rows.forEach((row) => {
      const matches = !query || row.dataset.packageName.includes(query);
      row.hidden = !matches;
      if (matches) visible += 1;
    });
    if (empty) empty.hidden = visible !== 0;
  };
  input.addEventListener("input", filter);
})();
