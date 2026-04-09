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

    // Обработчики кликов по карточкам
    grid.querySelectorAll('.product-card').forEach(card => {
      card.addEventListener('click', () => {
        const id = parseInt(card.dataset.id);
        Router.go('product', id);
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

    return `
      <article class="product-card" data-id="${p.id}">
        <div class="product-card__img-wrap">
          ${badge}
          <img class="product-card__img" src="${p.images[0]}" alt="${p.name}"
               data-loading="true" loading="lazy" width="300" height="400">
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
