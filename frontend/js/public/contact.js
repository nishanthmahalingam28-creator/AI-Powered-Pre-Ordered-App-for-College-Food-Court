document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('contact-form');
  const status = document.getElementById('contact-form-status');
  if (!form) return;

  const apiBase = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');
  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    const original = button ? button.innerHTML : '';
    if (button) { button.disabled = true; button.innerHTML = 'Sending... <i class="fa-solid fa-spinner fa-spin"></i>'; }
    if (status) { status.textContent = ''; status.className = 'mt-3 text-sm font-semibold'; }

    try {
      const response = await fetch(apiBase + '/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: document.getElementById('name')?.value.trim(),
          email: document.getElementById('email')?.value.trim(),
          subject: document.getElementById('subject')?.value.trim(),
          message: document.getElementById('message')?.value.trim()
        })
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || 'Unable to send your message.');
      if (status) { status.textContent = 'Thank you! Your message has been submitted to the Food Court administration.'; status.className = 'mt-3 text-sm font-semibold text-emerald-700'; }
      form.reset();
    } catch (error) {
      if (status) { status.textContent = error.message || 'Unable to send your message. Please try again.'; status.className = 'mt-3 text-sm font-semibold text-rose-700'; }
    } finally {
      if (button) { button.disabled = false; button.innerHTML = original; }
    }
  });
});
