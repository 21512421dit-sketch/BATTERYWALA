(() => {
  'use strict';

  const ready = () => {
    const logoPath = '/static/images/batterywala-logo-original.png';
    const heroPath = '/static/images/online-ups-smf-hero.png';
    const tractorPath = '/static/images/earth-movers-tractor.png';

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
      message.textContent = 'Choose the Battery from Top Brands fit for your requirements';
      right.append(message, nav, actions);
      headerWrap.append(right);
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
      'Doorstep Fitment',
      'Inverter and UPS Battery',
      'Industrial Battery',
      'Tubular and SMF Battery',
      'Forklift and Stacker Battery',
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
        node.nodeValue = node.nodeValue.replaceAll(from, to);
      });
    };
    replaceText(document.body, 'Battery Life cycle Restoration', 'Battery Backup Restoration Service');
    replaceText(document.body, 'Battery lifecycle assistance', 'Battery Backup Restoration Service');
    document.addEventListener('click', event => {
      if (!event.target.closest('.nextStep')) return;
      requestAnimationFrame(() => {
        const result = document.getElementById('resultText');
        if (result) result.textContent = result.textContent.replace(/\bbattery battery\b/gi, 'battery');
      });
    });

    const vehicles = document.getElementById('vehicles');
    const finderOptions = document.getElementById('finderOptions');
    const panel = document.querySelector('.vehiclePanel');
    const content = document.getElementById('vehicleContent');
    const largeVisual = document.getElementById('bigIcon');
    if (vehicles && finderOptions && panel && content && largeVisual) {
      const sourceCards = [...vehicles.querySelectorAll('.vehicle')];
      const extras = [
        {
          name: 'Earth Movers and Tractor',
          image: tractorPath,
          description: 'Rugged starting and power solutions for tractors, construction equipment and demanding off-road duty cycles.',
          chips: ['Tractor', 'Earth mover', 'Construction equipment']
        },
        {
          name: 'Online UPS and SMF Battery',
          source: sourceCards[3],
          description: 'Reliable online UPS and SMF battery-bank solutions for IT infrastructure, factories and critical operations.',
          chips: ['Online UPS', 'SMF bank', 'Critical backup']
        }
      ];

      extras.forEach((item, index) => {
        const sourceImage = item.source?.querySelector('img');
        const imagePath = item.image || sourceImage?.src || heroPath;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'vehicle bw-extra-vehicle';
        button.dataset.extra = String(index);
        button.innerHTML = `<img class="vehiclePhoto" src="${imagePath}" alt="${item.name} application"><strong>${item.name}</strong>`;
        vehicles.append(button);

        const option = document.createElement('button');
        option.type = 'button';
        option.className = 'option';
        option.dataset.name = item.name;
        option.textContent = item.name;
        finderOptions.append(option);
      });

      const scrollToPanel = () => panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      vehicles.addEventListener('click', event => {
        const button = event.target.closest('.bw-extra-vehicle');
        if (!button) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const item = extras[Number(button.dataset.extra)];
        vehicles.querySelectorAll('.vehicle').forEach(card => card.classList.toggle('active', card === button));
        const image = button.querySelector('img');
        largeVisual.innerHTML = `<img class="vehiclePhotoLarge" src="${image.src}" alt="${item.name} application">`;
        content.innerHTML = `<div class="tween"><span class="eyebrow">Selected application</span><h3>${item.name}</h3><p style="color:#c4cbea;line-height:1.7">${item.description}</p><div class="vehicleChips">${item.chips.map(chip => `<span class="chip">${chip}</span>`).join('')}</div><a class="btn primary" href="#battery-request">Find a solution →</a></div>`;
        scrollToPanel();
      }, true);

      vehicles.addEventListener('click', event => {
        if (event.target.closest('.vehicle')) requestAnimationFrame(scrollToPanel);
      });
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready, { once: true });
  else ready();
})();
