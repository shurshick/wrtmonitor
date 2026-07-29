(() => {
  const select = document.querySelector('[data-firmware-catalog]');
  if (!select) return;
  const form = select.closest('form');
  const url = form.querySelector('[data-firmware-url]');
  const sha = form.querySelector('[data-firmware-sha]');
  const model = form.querySelector('[data-firmware-model]');
  const update = () => {
    const item = select.selectedOptions[0];
    url.value = item?.value || '';
    sha.value = item?.dataset.sha256 || '';
    model.value = item?.dataset.model || '';
  };
  select.addEventListener('change', update);
  update();
})();
