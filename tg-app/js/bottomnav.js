/* ================================================
   НИЖНЯЯ НАВИГАЦИЯ — tap bar с 4 вкладками
   ================================================ */

const BottomNav = {
  /** Экраны, где показывается нижняя навигация */
  NAV_SCREENS: ['catalog', 'favorites', 'cart', 'profile', 'product'],

  /** Инициализация */
  init() {
    // Обработчики нажатий на вкладки
    document.querySelectorAll('.bottom-nav__item').forEach(item => {
      item.addEventListener('click', () => {
        const tab = item.dataset.tab;

        // Повторный тап — прокрутить наверх
        if (tab === Router.current) {
          const screen = document.getElementById('screen-' + tab);
          if (screen) screen.scrollTop = 0;
          return;
        }

        TG.hapticLight();
        Router.go(tab);
      });
    });

    // Обновлять бейдж корзины при изменениях в Store
    Store.onChange(() => BottomNav._updateBadge());
    BottomNav._updateBadge();

    // Начальное состояние — каталог активен
    BottomNav.setActive('catalog');
  },

  /**
   * Обновить активную вкладку и видимость панели
   * Вызывается из Router.onEnter в app.js
   */
  setActive(screen) {
    const nav = document.getElementById('bottom-nav');
    if (!nav) return;

    const visible = BottomNav.NAV_SCREENS.includes(screen);
    nav.classList.toggle('bottom-nav--hidden', !visible);

    // Подсветить нужную вкладку (карточка товара — подсвечиваем каталог)
    const activeTab = screen === 'product' ? 'catalog' : screen;
    document.querySelectorAll('.bottom-nav__item').forEach(item => {
      item.classList.toggle('bottom-nav__item--active', item.dataset.tab === activeTab);
    });
  },

  /** Обновить бейдж с числом товаров на вкладке «Корзина» */
  _updateBadge() {
    const count = Store.getCount();
    const badge = document.getElementById('nav-cart-badge');
    if (!badge) return;
    badge.textContent = count > 9 ? '9+' : count;
    badge.hidden = count === 0;
  }
};
