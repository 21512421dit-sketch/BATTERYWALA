(() => {
  'use strict';
  const form = document.getElementById('masterBatteryForm');
  if (!form) return;
  const panel = document.createElement('section');
  panel.className = 'bw-quotation';
  panel.hidden = true;
  panel.setAttribute('aria-label', 'Your quotation');
  panel.innerHTML = `
    <h3 tabindex="-1">Your quotation is ready</h3>
    <p data-quote-summary></p><p data-quote-note></p>
    <form data-quote-delivery>
      <h4>How should the quotation be sent to you?</h4>
      <p>Choose email, mobile number, or both.</p>
      <div class="field"><label for="quoteChannel">Send via</label>
        <select id="quoteChannel" name="channel" required>
          <option value="">Choose a delivery option</option><option value="email">Email</option>
          <option value="mobile">Mobile number</option><option value="both">Both</option>
        </select>
      </div>
      <div class="field" data-email-field hidden><label for="quoteEmail">Email address</label>
        <input id="quoteEmail" name="email" type="email" maxlength="255" autocomplete="email" disabled>
      </div>
      <div class="field" data-phone-field hidden><label for="quotePhone">Mobile number</label>
        <input id="quotePhone" name="phone" inputmode="numeric" pattern="[0-9]{10}" maxlength="10" autocomplete="tel-national" disabled>
      </div>
      <button class="btn primary" type="submit">Send quotation</button>
      <p data-delivery-status role="status" aria-live="polite"></p>
    </form>`;
  form.after(panel);
  const delivery = panel.querySelector('form');
  const status = panel.querySelector('[data-delivery-status]');
  const channel = delivery.elements.channel;
  let quote = null;
  const toggleFields = () => {
    ['email', 'phone'].forEach(name => {
      const visible = channel.value === 'both' || channel.value === (name === 'phone' ? 'mobile' : 'email');
      panel.querySelector(`[data-${name}-field]`).hidden = !visible;
      delivery.elements[name].disabled = !visible;
      delivery.elements[name].required = visible;
    });
  };
  channel.addEventListener('change', toggleFields);
  window.addEventListener('batterywala:submission', event => {
    quote = event.detail.prediction.quotation;
    if (!quote) return;
    delivery.reset();
    delivery.elements.email.value = event.detail.form.email || '';
    delivery.elements.phone.value = event.detail.form.phone || '';
    toggleFields();
    panel.querySelector('h3').textContent = quote.status === 'priced' ? 'Your quotation is ready' : 'Quotation generated — price confirmation required';
    panel.querySelector('[data-quote-summary]').textContent = `${quote.number} · ${quote.message}`;
    panel.querySelector('[data-quote-note]').textContent = quote.note;
    status.textContent = '';
    panel.hidden = false;
    panel.querySelector('h3').focus();
  });
  // Hide a previous quote when its source details are edited or reset.
  const clear = () => { panel.hidden = true; quote = null; };
  form.addEventListener('input', clear);
  form.addEventListener('change', clear);
  form.addEventListener('reset', clear);
  delivery.addEventListener('submit', async event => {
    event.preventDefault();
    if (!quote || !delivery.reportValidity()) return;
    const button = delivery.querySelector('button[type="submit"]');
    if (button.disabled) return;
    const activeQuote = quote;
    const payload = Object.fromEntries(new FormData(delivery));
    button.disabled = true;
    status.textContent = 'Sending your quotation…';
    try {
      const response = await fetch(activeQuote.send_url, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'ngrok-skip-browser-warning': '1'}, body: JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Unable to send the quotation.');
      if (quote === activeQuote) status.textContent = result.deliveries.map(item => `${item.channel === 'email' ? 'Email' : 'Mobile'}: ${item.message}`).join(' ');
    } catch (error) {
      if (quote === activeQuote) status.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
})();
