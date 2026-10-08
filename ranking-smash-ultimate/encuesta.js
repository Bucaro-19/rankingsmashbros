/* Optional presentation only: no requests, storage, analytics or answer persistence. */
(() => {
  const form = document.querySelector('.survey-form');
  if (!form) return;
  const segments = [...form.querySelectorAll('[data-question]')];
  const progress = document.getElementById('survey-progress-text');
  const comment = document.getElementById('comment');
  const counter = document.getElementById('comment-count');
  function update() {
    let answered = 0;
    segments.forEach((segment, i) => {
      const selected = !!form.querySelector(`input[name="${segment.dataset.question}"]:checked`);
      answered += Number(selected);
      segment.classList.toggle('answered', selected);
      if (selected) segment.classList.remove('missing');
      segment.setAttribute('aria-label', `Pregunta ${i + 1}: ${selected ? 'respondida' : 'sin responder'}`);
    });
    progress.textContent = `Respondiste ${answered} de 6`;
    counter.textContent = `${Array.from(comment.value).length} / 2,000`;
  }
  form.addEventListener('change', update);
  comment.addEventListener('input', update);
  form.addEventListener('submit', () => {
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    submit.classList.add('sending');
    submit.querySelector('span').textContent = 'Enviando…';
  });
  // A browser may restore the previous page from its back/forward cache.
  window.addEventListener('pageshow', () => {
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = false;
    submit.classList.remove('sending');
    submit.querySelector('span').innerHTML = 'ENVIAR OPINIÓN <b aria-hidden="true">↗</b>';
    update();
  });
  update();
  document.getElementById('survey-error')?.focus();
})();
