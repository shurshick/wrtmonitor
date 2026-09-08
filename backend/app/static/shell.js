(() => {
  const body = document.body;
  const nav = document.getElementById("device-sidebar");
  const navToggle = document.querySelector("[data-nav-toggle]");
  const navCollapse = document.querySelector("[data-nav-collapse]");
  const scrim = document.querySelector("[data-nav-scrim]");
  const compactQuery = matchMedia("(max-width: 1024px)");

  const announce = (message) => {
    const region = document.querySelector("[data-app-announcer]");
    if (region) region.textContent = message;
  };

  const closeNav = () => {
    const hadFocus = nav?.contains(document.activeElement);
    body.classList.remove("app-nav-open");
    if (navToggle) navToggle.setAttribute("aria-expanded", "false");
    if (nav) nav.inert = compactQuery.matches;
    if (scrim) scrim.hidden = true;
    if (hadFocus && compactQuery.matches) navToggle?.focus();
  };

  if (nav && navToggle) {
    nav.inert = compactQuery.matches;
    const savedCollapsed = localStorage.getItem("wrtmonitor-sidebar") === "collapsed";
    body.classList.toggle("app-nav-collapsed", savedCollapsed && !compactQuery.matches);
    navToggle.addEventListener("click", () => {
      if (compactQuery.matches) {
        const open = !body.classList.contains("app-nav-open");
        body.classList.toggle("app-nav-open", open);
        nav.inert = !open;
        navToggle.setAttribute("aria-expanded", String(open));
        if (scrim) scrim.hidden = !open;
        if (open) nav.querySelector("a")?.focus();
      } else {
        body.classList.toggle("app-nav-collapsed");
        const collapsed = body.classList.contains("app-nav-collapsed");
        localStorage.setItem("wrtmonitor-sidebar", collapsed ? "collapsed" : "expanded");
        announce(collapsed ? "Боковая панель свёрнута" : "Боковая панель развёрнута");
      }
    });
    navCollapse?.addEventListener("click", () => navToggle.click());
    scrim?.addEventListener("click", closeNav);
    compactQuery.addEventListener("change", () => {
      closeNav();
      body.classList.toggle("app-nav-collapsed", !compactQuery.matches && localStorage.getItem("wrtmonitor-sidebar") === "collapsed");
    });
  } else if (navToggle) {
    navToggle.hidden = true;
  }

  const selector = document.querySelector("[data-router-selector]");
  if (selector) {
    const button = selector.querySelector("[data-router-selector-toggle]");
    const popover = selector.querySelector("[data-router-selector-popover]");
    const list = selector.querySelector("[data-router-list]");
    const search = selector.querySelector("[data-router-search]");
    let loaded = false;

    const closeSelector = () => {
      popover.hidden = true;
      button.setAttribute("aria-expanded", "false");
    };
    const renderRouters = (documentFragment) => {
      list.replaceChildren();
      documentFragment.querySelectorAll(".router-card").forEach((card) => {
        const sourceLink = card.querySelector(".router-card__main");
        const row = document.createElement("a");
        const identity = document.createElement("span");
        const state = document.createElement("span");
        row.className = "router-selector__item";
        row.href = sourceLink?.getAttribute("href") || "/devices";
        row.dataset.searchValue = card.textContent.toLowerCase();
        if (row.href.endsWith(`/${selector.dataset.currentDevice}`)) row.classList.add("is-current");
        identity.className = "router-selector__item-copy";
        const name = document.createElement("strong");
        const details = document.createElement("small");
        name.textContent = card.querySelector(".router-card__identity strong")?.textContent || "Роутер";
        details.textContent = card.querySelector(".router-card__identity small")?.textContent || "OpenWrt";
        identity.append(name, details);
        state.className = card.querySelector(".status")?.className || "status";
        state.textContent = card.querySelector(".status")?.textContent || "Нет данных";
        row.append(identity, state);
        list.append(row);
      });
      if (!list.children.length) {
        const empty = document.createElement("span");
        empty.className = "router-selector__loading";
        empty.textContent = "Роутеры не найдены";
        list.append(empty);
      }
      loaded = true;
    };
    const loadRouters = async () => {
      if (loaded) return;
      try {
        const response = await fetch("/devices", { credentials: "same-origin" });
        if (!response.ok) throw new Error("router list unavailable");
        const html = await response.text();
        renderRouters(new DOMParser().parseFromString(html, "text/html"));
      } catch {
        list.textContent = "Не удалось загрузить список. Откройте все роутеры.";
      }
    };
    button.addEventListener("click", async () => {
      const open = popover.hidden;
      if (!open) return closeSelector();
      popover.hidden = false;
      button.setAttribute("aria-expanded", "true");
      await loadRouters();
      search.focus();
    });
    search.addEventListener("input", () => {
      const query = search.value.trim().toLowerCase();
      list.querySelectorAll(".router-selector__item").forEach((row) => {
        row.hidden = !row.dataset.searchValue.includes(query);
      });
    });
    document.addEventListener("click", (event) => {
      if (!selector.contains(event.target)) closeSelector();
    });
  }

  let dirtyForm = null;
  const dirtyBar = document.createElement("div");
  dirtyBar.className = "dirty-bar";
  dirtyBar.hidden = true;
  dirtyBar.innerHTML = '<span><strong>Есть несохранённые изменения</strong><small>Проверьте их перед применением.</small></span><div><button class="button button--secondary" type="button" data-dirty-reset>Сбросить</button><button type="button" data-dirty-submit>Проверить и применить</button></div>';
  body.append(dirtyBar);
  document.querySelectorAll('form[action*="/web-command"]').forEach((form) => {
    form.addEventListener("change", () => {
      dirtyForm = form;
      dirtyBar.hidden = false;
    });
    form.addEventListener("submit", () => { dirtyBar.hidden = true; });
  });
  dirtyBar.querySelector("[data-dirty-reset]").addEventListener("click", () => {
    dirtyForm?.reset();
    dirtyForm = null;
    dirtyBar.hidden = true;
    announce("Изменения сброшены");
  });
  dirtyBar.querySelector("[data-dirty-submit]").addEventListener("click", () => dirtyForm?.requestSubmit());

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    closeNav();
    selector?.querySelector("[data-router-selector-popover]")?.setAttribute("hidden", "");
    const selectorButton = selector?.querySelector("[data-router-selector-toggle]");
    if (selectorButton?.getAttribute("aria-expanded") === "true") {
      selectorButton.setAttribute("aria-expanded", "false");
      selectorButton.focus();
    }
  });
})();
