/* ================================================
   APP — точка входа, инициализация всех модулей
   ================================================ */

/** Утилита для bottom sheet */
const BottomSheet = {
  _current: null,

  open(id) {
    const sheet = document.getElementById(id);
    if (!sheet) return;
    sheet.hidden = false;
    // Форсируем reflow для анимации
    sheet.offsetHeight;
    sheet.classList.add('open');
    BottomSheet._current = sheet;

    // Закрытие по тапу на backdrop
    const backdrop = sheet.querySelector('.bottom-sheet__backdrop');
    backdrop.addEventListener('click', BottomSheet.close, { once: true });
  },

  close() {
    if (!BottomSheet._current) return;
    const sheet = BottomSheet._current;
    sheet.classList.remove('open');
    setTimeout(() => {
      sheet.hidden = true;
    }, 250);
    BottomSheet._current = null;
  }
};

/* --- Оффер при первом открытии --- */

const Offer = {
  STORAGE_KEY: 'mia_offer_seen',

  show() {
    // Показываем пока не взята скидка — даже если уже видели и пропустили
    if (localStorage.getItem('mia_discount')) return;

    const overlay = document.getElementById('offer-overlay');
    overlay.classList.add('visible');

    document.getElementById('offer-btn-skip').addEventListener('click', () => Offer.close());
    document.getElementById('offer-btn-subscribe').addEventListener('click', () => {
      TG.hapticLight();
      Store.setDiscount(0.1);
      TG.openTelegramLink('https://t.me/sikretsweet_home_bot?start=from_app');
      Offer.close();
    });
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) Offer.close();
    });
  },

  close() {
    const overlay = document.getElementById('offer-overlay');
    overlay.classList.remove('visible');
  }
};

/* --- Инициализация приложения --- */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Telegram SDK
  TG.init();

  // 2. Хранилище корзины
  Store.init();
  Store.loadDiscount();

  // 3. Обновление бейджа при любом изменении корзины
  Store.onChange(() => {
    const count = Store.getCount();
    const badge = document.getElementById('cart-badge');
    if (count > 0) {
      badge.textContent = count;
      badge.hidden = false;
      badge.classList.remove('pulse');
      badge.offsetHeight; // reflow
      badge.classList.add('pulse');
    } else {
      badge.hidden = true;
    }
  });

  // 4. Инициализация всех экранов
  Catalog.init();
  Product.init();
  Cart.init();
  Checkout.init();
  Success.init();

  // 5. Роутер: колбэки при входе на каждый экран
  Router.onEnter('catalog', () => {
    TG.hideMainButton();
    TG.hideBackButton();
    Catalog.render();
  });

  Router.onEnter('product', (productId) => {
    Product.show(productId);
  });

  Router.onEnter('cart', () => {
    Cart.show();
  });

  Router.onEnter('checkout', () => {
    Checkout.show();
  });

  Router.onEnter('success', (order) => {
    Success.show(order);
  });

  // 6. Оффер — показываем один раз при первом запуске
  setTimeout(() => Offer.show(), 600);
});
