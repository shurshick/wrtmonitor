(() => {
  const root = document.documentElement;
  const button = document.querySelector("[data-theme-toggle]");
  const icon = document.querySelector("[data-theme-icon]");

  if (!button || !icon) return;

  const render = () => {
    const isDark = root.dataset.theme !== "light";
    icon.textContent = isDark ? "☀" : "☾";
    const label = isDark ? "Включить светлую тему" : "Включить тёмную тему";
    button.title = label;
    button.setAttribute("aria-label", label);
    button.setAttribute("aria-pressed", String(!isDark));
  };

  button.addEventListener("click", () => {
    const next = root.dataset.theme === "light" ? "dark" : "light";
    root.dataset.theme = next;
    localStorage.setItem("wrtmonitor-theme", next);
    render();
  });

  render();
})();
