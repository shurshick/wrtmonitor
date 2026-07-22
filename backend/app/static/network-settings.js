(() => {
  const form = document.querySelector('[data-wan-form]');
  if (!form) return;
  const protocol = form.querySelector('[data-wan-protocol]');
  const groups = [...form.querySelectorAll('[data-wan-fields]')];
  const update = () => {
    const selected = protocol.value;
    groups.forEach((group) => {
      const visible = group.dataset.wanFields.split(/\s+/).includes(selected);
      group.hidden = !visible;
      group.querySelectorAll('input, select').forEach((input) => { input.disabled = !visible; });
    });
  };
  protocol.addEventListener('change', update);
  update();
})();
