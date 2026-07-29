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

(() => {
  const profile = document.querySelector('[data-sqm-profile]');
  if (!profile) return;
  const form = profile.closest('form');
  const qdisc = form.querySelector('[data-sqm-qdisc]');
  const script = form.querySelector('[data-sqm-script]');
  const options = form.querySelector('[data-sqm-options]');
  const update = () => {
    const selected = profile.selectedOptions[0];
    if (!selected || selected.value === 'custom') return;
    qdisc.value = selected.dataset.qdisc || 'cake';
    script.value = selected.dataset.script || 'piece_of_cake.qos';
    options.value = selected.dataset.options || '';
  };
  profile.addEventListener('change', update);
  update();
})();
