/* ================================================
   ИЗБРАННОЕ — список желаний
   ================================================ */

const Favorites = {
  STORAGE_KEY: 'mia_favorites',

  /** Множество id избранных товаров */
  _ids: new Set(),

  /** Инициализация */
  init() {
    try {
      const saved = localStorage.getItem(Favorites.STORAGE_KEY);
      if (saved) Favorites._ids = new Set(JSON.parse(saved));
    } catch {}

    document.getElementById('btn-to-catalog-from-fav')?.addEventListener('click', () => {
      TG.hapticLight();
      Router.go('catalog');
    });
  },

  /** Переключить избранное у товара, вернуть новое состояние */
  toggle(id) {
    if (Favorites._ids.has(id)) {
      Favorites._ids.delete(id);
      TG.hapticLight();
    } else {
      Favorites._ids.add(id);
      TG.hapticSuccess();
    }
    Favorites._save();
    return Favorites._ids.has(id);
  },

  /** Проверить, в избранном ли товар */
  has(id) {
    return Favorites._ids.has(id);
  },

  /** Обновить иконку сердца в текущем каталоге/избранном */
  updateHeart(id) {
    const isFav = Favorites.has(id);
    document.querySelectorAll(`[data-heart-id="${id}"]`).forEach(btn => {
      btn.classList.toggle('product-card__heart--active', isFav);
    });
  },

  /** Отрисовать экран избранного */
  render() {
    const grid = document.getElementById('favorites-grid');
    const empty = document.getElementById('favorites-empty');
    const products = (Catalog._products || []).filter(p => Favorites._ids.has(p.id));

    if (products.length === 0) {
      grid.innerHTML = '';
      empty.hidden = false;
      return;
    }

    empty.hidden = true;
    grid.innerHTML = products.map(p => Catalog._cardHTML(p)).join('');

    // Обработчик клика по карточке (переход на товар)
    grid.querySelectorAll('.product-card').forEach(card => {
      card.addEventListener('click', (e) => {
        if (e.target.closest('.product-card__heart')) return;
        Router.go('product', parseInt(card.dataset.id));
      });
    });

    // Обработчик сердечек
    grid.querySelectorAll('.product-card__heart').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = parseInt(btn.dataset.heartId);
        const isNow = Favorites.toggle(id);
        btn.classList.toggle('product-card__heart--active', isNow);
        // Если сняли из избранного — перерисовать список
        if (!isNow) setTimeout(() => Favorites.render(), 200);
      });
    });

    // Lazy load
    grid.querySelectorAll('.product-card__img').forEach(img => {
      img.onload = () => img.removeAttribute('data-loading');
      if (img.complete) img.removeAttribute('data-loading');
    });
  },

  _save() {
    localStorage.setItem(Favorites.STORAGE_KEY, JSON.stringify([...Favorites._ids]));
  }
};
