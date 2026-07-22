(() => {
  const countdown = document.querySelector("[data-pairing-countdown]");
  if (!countdown) return;

  const expiresAt = Date.parse(countdown.dataset.expiresAt || "");
  const status = document.querySelector("[data-pairing-status]");
  const update = () => {
    const remaining = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
    const minutes = Math.floor(remaining / 60);
    const seconds = remaining % 60;
    countdown.textContent = `${minutes}:${String(seconds).padStart(2, "0")}`;
    if (remaining === 0 && status) {
      status.textContent = "истёк";
      status.classList.remove("status--online");
      status.classList.add("status--offline");
    }
    return remaining;
  };
  update();
  const timer = window.setInterval(() => {
    if (update() === 0) window.clearInterval(timer);
  }, 1000);
})();
