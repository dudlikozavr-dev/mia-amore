/* ================================================
   КАТАЛОГ — отрисовка сетки товаров + фильтры
   ================================================ */

const Catalog = {
  /** Текущий активный фильтр */
  _filter: 'all',

  /** Инициализация */
  init() {
    // Обработчик фильтров
    document.getElementById('filters').addEventListener('click', e => {
      const chip = e.target.closest('.chip');
      if (!chip) return;

      TG.hapticSelection();

      // Переключить активный чип
      document.querySelectorAll('#filters .chip').forEach(c => c.classList.remove('chip--active'));
      chip.classList.add('chip--active');

      Catalog._filter = chip.dataset.filter;
      Catalog.render();
    });

    // Кнопка «Сбросить фильтры»
    document.getElementById('btn-reset-filters')?.addEventListener('click', () => {
      Catalog._filter = 'all';
      document.querySelectorAll('#filters .chip').forEach(c => c.classList.remove('chip--active'));
      document.querySelector('[data-filter="all"]')?.classList.add('chip--active');
      Catalog.render();
    });

    // Кнопка корзины
    document.getElementById('btn-open-cart').addEventListener('click', () => {
      Router.go('cart');
    });

    // Первый рендер
    Catalog.render();
  },

  /** Отфильтровать товары */
  _getFiltered() {
    if (Catalog._filter === 'all') return PRODUCTS;
    return PRODUCTS.filter(p =>
      p.category === Catalog._filter || p.material === Catalog._filter
    );
  },

  /** Отрисовка сетки */
  render() {
    const grid = document.getElementById('catalog-grid');
    const empty = document.getElementById('catalog-empty');
    const items = Catalog._getFiltered();

    if (items.length === 0) {
      grid.innerHTML = '';
      empty.hidden = false;
      return;
    }

    empty.hidden = true;
    grid.innerHTML = items.map(p => Catalog._cardHTML(p)).join('');

    // Обработчики кликов по карточкам (игнорировать клик на сердце)
    grid.querySelectorAll('.product-card').forEach(card => {
      card.addEventListener('click', (e) => {
        if (e.target.closest('.product-card__heart')) return;
        const id = parseInt(card.dataset.id);
        Router.go('product', id);
      });
    });

    // Обработчики кнопок «избранное»
    grid.querySelectorAll('.product-card__heart').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.heartId);
        const isNow = Favorites.toggle(id);
        btn.classList.toggle('product-card__heart--active', isNow);
        // Анимация пульса
        btn.classList.remove('heart-pop');
        btn.offsetHeight; // reflow
        btn.classList.add('heart-pop');
        // Обновить SVG fill
        const path = btn.querySelector('svg path');
        if (path) path.setAttribute('fill', isNow ? 'currentColor' : 'none');
      });
    });

    // Lazy load фото
    grid.querySelectorAll('.product-card__img').forEach(img => {
      img.onload = () => img.removeAttribute('data-loading');
      if (img.complete) img.removeAttribute('data-loading');
    });
  },

  /** HTML одной карточки */
  _cardHTML(p) {
    let badge = '';
    if (p.badge === 'hit') badge = '<span class="product-card__badge product-card__badge--hit">Хит</span>';
    if (p.badge === 'new') badge = '<span class="product-card__badge product-card__badge--new">Новинка</span>';
    if (p.stock <= 3) badge = `<span class="product-card__badge product-card__badge--low">Осталось ${p.stock}</span>`;

    const oldPrice = p.oldPrice
      ? `<span class="product-card__old-price">${Catalog._fmt(p.oldPrice)}</span>`
      : '';

    const isFav = typeof Favorites !== 'undefined' && Favorites.has(p.id);

    return `
      <article class="product-card" data-id="${p.id}">
        <div class="product-card__img-wrap">
          ${badge}
          <img class="product-card__img" src="${p.images[0]}" alt="${p.name}"
               data-loading="true" loading="lazy" width="300" height="400">
          <button class="product-card__heart ${isFav ? 'product-card__heart--active' : ''}"
                  data-heart-id="${p.id}" aria-label="В избранное">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="${isFav ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
            </svg>
          </button>
        </div>
        <div class="product-card__body">
          <div class="product-card__name">${p.name}</div>
          <div class="product-card__price-row">
            <span class="product-card__price">${Catalog._fmt(p.price)}</span>
            ${oldPrice}
          </div>
          <div class="product-card__material">${p.materialLabel}</div>
        </div>
      </article>
    `;
  },

  /** Форматирование цены */
  _fmt(n) {
    return n.toLocaleString('ru-RU') + ' ₽';
  }
};
