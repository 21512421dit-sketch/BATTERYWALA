(() => {
  'use strict';

  const ready = () => {
    const logoPath = '/static/images/batterywala-logo-original.png';
    const heroPath = '/static/images/online-ups-smf-hero.png';
    const tractorPath = '/static/images/earth-movers-tractor.png';
    const generatorPath = '/static/images/generator-battery.png';

    const header = document.querySelector('.header');
    const headerWrap = header?.querySelector('.wrap');
    const nav = header?.querySelector('.nav');
    const actions = header?.querySelector('.actions');
    if (header && headerWrap && nav && actions) {
      header.classList.add('bw-updated-header');
      const right = document.createElement('div');
      right.className = 'bw-header-right';
      const message = document.createElement('p');
      message.className = 'bw-header-message';
      const messageText = document.createElement('span');
      messageText.textContent = 'Choose the Battery from Top Brands fit for your requirements';
      message.append(messageText);
      const row = document.createElement('div');
      row.className = 'bw-header-row';
      row.append(nav, actions);
      right.append(message, row);
      headerWrap.append(right);

      const alignHeaderRow = () => {
        if (window.innerWidth <= 820) {
          row.style.removeProperty('width');
          return;
        }
        const rightBox = right.getBoundingClientRect();
        const textBox = messageText.getBoundingClientRect();
        row.style.width = `${Math.max(0, rightBox.right - textBox.left)}px`;
      };
      requestAnimationFrame(alignHeaderRow);
      document.fonts?.ready.then(alignHeaderRow);
      window.addEventListener('resize', alignHeaderRow, { passive: true });
    }

    const headerLogo = document.querySelector('.header .logoImage img');
    if (headerLogo) {
      headerLogo.src = logoPath;
      headerLogo.alt = 'BatteryWala — Trusted Power. Anytime, Anywhere.';
      headerLogo.removeAttribute('width');
      headerLogo.removeAttribute('height');
    }

    const heroSlide = document.querySelector('.hero .slide:nth-of-type(3)');
    if (heroSlide) {
      heroSlide.classList.add('bw-online-ups-slide');
      const image = heroSlide.querySelector('img');
      if (image) {
        image.src = heroPath;
        image.alt = 'SMF battery bank connected to an online UPS in a modern IT and manufacturing facility';
      }
      const eyebrow = heroSlide.querySelector('.eyebrow');
      const title = heroSlide.querySelector('h1');
      const copy = heroSlide.querySelector('p');
      if (eyebrow) eyebrow.textContent = 'Enterprise backup power';
      if (title) title.innerHTML = 'Online UPS power.<br>Always protected.';
      if (copy) copy.textContent = 'SMF battery banks and online UPS solutions designed for dependable uptime across IT and manufacturing facilities.';
    }

    document.querySelector('#supportOpen')?.remove();
    document.querySelector('.drawer')?.remove();
    document.querySelector('.drawerBack')?.remove();
    document.querySelector('#restoreBack')?.remove();
    document.querySelector('#restoreNudge')?.remove();
    document.body.classList.remove('lock');

    document.querySelectorAll('button[data-drawer]').forEach(button => {
      const link = document.createElement('a');
      link.className = button.className;
      link.href = '#battery-request';
      link.innerHTML = button.innerHTML;
      link.removeAttribute('data-drawer');
      button.replaceWith(link);
    });

    const stripItems = [
      'Automotive Battery',
      'Doorstep Fitment',
      'Home Backup Power',
      'Battery Diagnostics',
      'Commercial Fleets',
      'Battery Backup Restoration Service'
    ];
    document.querySelectorAll('.dynamicTrack').forEach(track => {
      const repeated = [...stripItems, ...stripItems];
      track.innerHTML = repeated.map(item => `<span><b>●</b>${item}</span>`).join('');
    });

    const replaceText = (root, from, to) => {
      if (!root) return;
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      nodes.forEach(node => {
        if (node.parentElement?.closest('script,style')) return;
        node.nodeValue = node.nodeValue.replace(from, to);
      });
    };
    replaceText(document.body, /battery[ -]health/gi, 'Battery Backup Restoration Service');
    replaceText(document.body, /health checks/gi, 'service checks');
    replaceText(document.body, /Battery Life cycle Restoration/gi, 'Battery Backup Restoration Service');
    replaceText(document.body, /Battery lifecycle assistance/gi, 'Battery Backup Restoration Service');
    replaceText(document.body, /Automobile Batter(?:y|ies)/gi, 'Automotive Battery');
    replaceText(document.body, /\bregeneration\b/gi, 'Battery Backup Restoration');

    document.querySelectorAll('a[href="#finder"]').forEach(link => {
      link.href = '#applications';
    });
    document.querySelector('.nav a[href="#applications"]')?.nextElementSibling?.matches('a[href="#applications"]') &&
      document.querySelector('.nav a[href="#applications"]')?.nextElementSibling?.remove();
    document.getElementById('finder')?.remove();

    const quickRestoration = document.querySelector('.quickbar .quick:last-child');
    if (quickRestoration) {
      const title = quickRestoration.querySelector('strong');
      const copy = quickRestoration.querySelector('small');
      if (title) title.textContent = 'Battery Backup Restoration Service';
      if (copy) copy.textContent = 'Technical battery regeneration service';
    }

    const serviceCards = [...document.querySelectorAll('#services .service')];
    const restorationCard = serviceCards[2];
    const diagnosticsCard = serviceCards[1];
    if (diagnosticsCard) {
      const copy = diagnosticsCard.querySelector('p');
      if (copy) copy.textContent = 'Battery condition diagnostics and practical next steps based on performance, condition and use case.';
    }
    if (restorationCard) {
      const eyebrow = restorationCard.querySelector('.eyebrow');
      const title = restorationCard.querySelector('h3');
      const copy = restorationCard.querySelector('p');
      if (eyebrow) eyebrow.textContent = '03 · Battery Backup Restoration Service';
      if (title) title.textContent = 'Restore dependable battery backup';
      if (copy) copy.textContent = 'Our Battery Backup Restoration Service is technically a battery regeneration service for eligible batteries, helping recover backup performance before replacement is considered.';
    }

    const restorationReason = [...document.querySelectorAll('.reason')]
      .find(reason => reason.querySelector('b')?.textContent.trim() === '04');
    if (restorationReason) {
      const title = restorationReason.querySelector('h4');
      const copy = restorationReason.querySelector('p');
      if (title) title.textContent = 'Battery Backup Restoration Service';
      if (copy) copy.textContent = 'Technical battery regeneration for eligible batteries can restore useful backup performance and reduce unnecessary replacement.';
    }
    document.addEventListener('click', event => {
      if (!event.target.closest('.nextStep')) return;
      requestAnimationFrame(() => {
        const result = document.getElementById('resultText');
        if (result) result.textContent = result.textContent.replace(/\bbattery battery\b/gi, 'battery');
      });
    });

    const vehicles = document.getElementById('vehicles');
    const panel = document.querySelector('.vehiclePanel');
    const content = document.getElementById('vehicleContent');
    const largeVisual = document.getElementById('bigIcon');
    if (vehicles && panel && content && largeVisual) {
      const sourceCards = [...vehicles.querySelectorAll('.vehicle')];
      const sourceImage = index => sourceCards[index]?.querySelector('img')?.src;
      const applications = [
        {
          name: 'Two & Three Wheeler',
          image: sourceImage(0),
          description: 'Dependable starting power for motorcycles, scooters, three-wheelers and everyday mobility.',
          chips: ['Motorcycle', 'Scooter', 'Three-wheeler']
        },
        {
          name: 'Car & SUV',
          image: sourceImage(1),
          description: 'Correctly matched starting batteries for hatchbacks, sedans, SUVs and premium passenger vehicles.',
          chips: ['Car', 'SUV', 'Passenger vehicle']
        },
        {
          name: 'Earth Mover & Tractor',
          image: tractorPath,
          description: 'Rugged starting and power solutions for tractors, construction equipment and demanding off-road duty cycles.',
          chips: ['Tractor', 'Earth mover', 'Construction equipment']
        },
        {
          name: 'Bus, Truck & Commercial Vehicle',
          image: sourceImage(2),
          description: 'Heavy-duty batteries and support workflows designed around commercial vehicle and fleet uptime.',
          chips: ['Bus', 'Truck', 'Commercial fleet']
        },
        {
          name: 'Generator Battery',
          image: generatorPath,
          description: 'Reliable starting batteries for generators serving homes, businesses and critical facilities.',
          chips: ['Generator', 'Standby power', 'Industrial']
        },
        {
          name: 'Tubular Battery',
          image: sourceImage(3),
          description: 'Long-duration tubular battery solutions for inverter and home backup applications.',
          chips: ['Inverter', 'Home backup', 'Long duration']
        },
        {
          name: 'SMF Battery',
          image: heroPath,
          description: 'Sealed maintenance-free batteries for UPS systems, IT infrastructure and critical backup.',
          chips: ['SMF', 'Online UPS', 'Critical backup']
        },
        {
          name: 'Traction Battery',
          image: sourceImage(4),
          description: 'Deep-cycle traction power for forklifts, stackers and material-handling equipment.',
          chips: ['Forklift', 'Stacker', 'Material handling']
        }
      ];

      vehicles.innerHTML = '';
      applications.forEach((item, index) => {
        const imagePath = item.image || heroPath;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `vehicle bw-application${index === 0 ? ' active' : ''}`;
        button.dataset.application = String(index);
        button.innerHTML = `<img class="vehiclePhoto" src="${imagePath}" alt="${item.name} application"><strong>${item.name}</strong>`;
        vehicles.append(button);
      });

      const scrollToPanel = () => panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      const showApplication = index => {
        const item = applications[index];
        const button = vehicles.querySelector(`[data-application="${index}"]`);
        vehicles.querySelectorAll('.vehicle').forEach(card => card.classList.toggle('active', card === button));
        largeVisual.innerHTML = `<img class="vehiclePhotoLarge" src="${item.image || heroPath}" alt="${item.name} application">`;
        content.innerHTML = `<div class="tween"><span class="eyebrow">Selected application</span><h3>${item.name}</h3><p style="color:#c4cbea;line-height:1.7">${item.description}</p><div class="vehicleChips">${item.chips.map(chip => `<span class="chip">${chip}</span>`).join('')}</div><a class="btn primary" href="#battery-request">Find a solution →</a></div>`;
      };
      showApplication(0);
      vehicles.addEventListener('click', event => {
        const button = event.target.closest('.bw-application');
        if (!button) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        showApplication(Number(button.dataset.application));
        scrollToPanel();
      }, true);
    }

    const requestForm = document.getElementById('masterBatteryForm');
    if (requestForm) {
      const predictionPanel = requestForm.querySelector('#bwPrediction');
      requestForm.innerHTML = `
        <p class="bw-progressive-hint">Choose the requirement and application. The relevant questions will appear automatically.</p>
        <div class="bw-form-grid">
          <div class="field"><label for="bwSolutionType">Requirement *</label><select id="bwSolutionType" name="solution_type" required><option value="">Select</option></select></div>
          <div class="field"><label for="bwApplicationKey">Battery application *</label><select id="bwApplicationKey" name="application_key" required disabled><option value="">Select a requirement first</option></select></div>
        </div>
        <p class="bw-schema-note" data-schema-note role="status"></p>
        <div class="bw-form-grid" data-dynamic-fields></div>
        <input type="hidden" name="application"><input type="hidden" name="battery_type">
        <div class="bw-prediction" id="bwPrediction"></div>
        <div class="formNav"><button class="btn primary" type="submit">Generate quotation</button><button class="btn light" type="reset">Reset</button></div>`;
      if (predictionPanel) requestForm.querySelector('#bwPrediction').replaceWith(predictionPanel);
      const modeSelect = requestForm.elements.solution_type;
      const applicationSelect = requestForm.elements.application_key;
      const fieldsHost = requestForm.querySelector('[data-dynamic-fields]');
      const note = requestForm.querySelector('[data-schema-note]');
      requestForm.addEventListener('reset', () => {
        predictionPanel.replaceChildren();
        predictionPanel.style.display = 'none';
      });
      const option = (value, label) => {
        const item = document.createElement('option'); item.value = value; item.textContent = label; return item;
      };
      const renderFields = schema => {
        fieldsHost.replaceChildren();
        schema.fields.forEach(field => {
          let control;
          if (field.type === 'hidden') {
            control = document.createElement('input'); control.type = 'hidden'; control.name = field.name; control.value = field.value || '';
            fieldsHost.append(control); return;
          }
          const wrapper = document.createElement('div'); wrapper.className = `field${field.type === 'textarea' ? ' bw-wide' : ''}`;
          const label = document.createElement('label'); label.textContent = `${field.label}${field.required ? ' *' : ''}`;
          if (field.type === 'select') {
            control = document.createElement('select'); control.append(option('', 'Select'));
            (field.options || []).forEach(item => control.append(option(typeof item === 'string' ? item : item.value, typeof item === 'string' ? item : item.label)));
          } else if (field.type === 'textarea') control = document.createElement('textarea');
          else { control = document.createElement('input'); control.type = field.type || 'text'; }
          control.name = field.name; control.id = `bw-${field.name}`; label.htmlFor = control.id;
          if (field.pattern) control.pattern = field.pattern;
          if (field.min !== undefined) control.min = field.min;
          if (field.required) control.dataset.schemaRequired = 'true';
          if (field.show_when) wrapper.dataset.showWhen = JSON.stringify(field.show_when);
          wrapper.append(label, control); fieldsHost.append(wrapper);
        });
        const updateConditions = () => fieldsHost.querySelectorAll('[data-show-when]').forEach(wrapper => {
          const conditions = JSON.parse(wrapper.dataset.showWhen);
          const visible = Object.entries(conditions).every(([name, value]) => requestForm.elements[name]?.value === String(value));
          wrapper.hidden = !visible;
          const control = wrapper.querySelector('input,select,textarea'); control.disabled = !visible; control.required = visible && control.dataset.schemaRequired === 'true';
        });
        fieldsHost.addEventListener('change', updateConditions); updateConditions();
      };
      fetch('/api/form-schemas', {headers: {'ngrok-skip-browser-warning': '1'}}).then(response => {
        if (!response.ok) throw new Error('Unable to load form options');
        return response.json();
      }).then(schemas => {
        Object.entries(schemas).forEach(([key, value]) => modeSelect.append(option(key, value.label)));
        modeSelect.addEventListener('change', () => {
          applicationSelect.replaceChildren(option('', modeSelect.value ? 'Select' : 'Select a requirement first'));
          applicationSelect.disabled = !modeSelect.value; fieldsHost.replaceChildren(); note.textContent = schemas[modeSelect.value]?.note || '';
          Object.entries(schemas[modeSelect.value]?.applications || {}).forEach(([key, value]) => applicationSelect.append(option(key, value.label)));
        });
        applicationSelect.addEventListener('change', () => {
          const schema = schemas[modeSelect.value]?.applications[applicationSelect.value];
          requestForm.elements.application.value = schema?.label || '';
          requestForm.elements.battery_type.value = schemas[modeSelect.value]?.label || '';
          if (schema) renderFields(schema); else fieldsHost.replaceChildren();
        });
        requestForm.addEventListener('reset', () => setTimeout(() => {
          applicationSelect.replaceChildren(option('', 'Select a requirement first')); applicationSelect.disabled = true; fieldsHost.replaceChildren(); note.textContent = '';
        }, 0));
      }).catch(error => { note.textContent = error.message + '. Please refresh the page.'; });
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready, { once: true });
  else ready();
})();
