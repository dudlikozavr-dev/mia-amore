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

/* --- Онбординг (показывается один раз) --- */

const Onboarding = {
  STORAGE_KEY: 'mia_onboarding_done',

  show() {
    if (localStorage.getItem(this.STORAGE_KEY)) return;

    const overlay = document.getElementById('onboarding-overlay');

    // Приветствие по имени из Telegram
    const user = TG.getUser();
    if (user && user.first_name) {
      document.getElementById('onboarding-title').textContent = `Привет, ${user.first_name}! 👋`;
    }

    overlay.classList.add('visible');

    document.getElementById('onboarding-btn-start').addEventListener('click', () => {
      TG.hapticLight();
      localStorage.setItem(Onboarding.STORAGE_KEY, '1');
      overlay.classList.remove('visible');
      // После онбординга показать оффер
      setTimeout(() => Offer.show(), 400);
    });
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
  Favorites.init();
  Profile.init();
  BottomNav.init();
  Product.init();
  Cart.init();
  Checkout.init();
  Success.init();

  // 5. Роутер: колбэки при входе на каждый экран
  Router.onEnter('catalog', () => {
    TG.hideMainButton();
    TG.hideBackButton();
    Catalog.render();
    BottomNav.setActive('catalog');
  });

  Router.onEnter('favorites', () => {
    TG.hideMainButton();
    TG.hideBackButton();
    Favorites.render();
    BottomNav.setActive('favorites');
  });

  Router.onEnter('profile', () => {
    TG.hideMainButton();
    TG.hideBackButton();
    Profile.show();
    BottomNav.setActive('profile');
  });

  Router.onEnter('cart', () => {
    Cart.show();
    BottomNav.setActive('cart');
  });

  Router.onEnter('product', (productId) => {
    Product.show(productId);
    BottomNav.setActive('product');
  });

  Router.onEnter('checkout', () => {
    Checkout.show();
    BottomNav.setActive('checkout');
  });

  Router.onEnter('success', (order) => {
    Success.show(order);
    BottomNav.setActive('success');
  });

  // 6. Кнопка «Поделиться»
  document.getElementById('btn-share').addEventListener('click', () => {
    TG.hapticLight();
    const text = 'Смотри, нашла классный магазин шёлковой домашней одежды 🌸';
    const url = 'https://t.me/sikretsweet_home_bot/app';
    if (window.Telegram?.WebApp?.switchInlineQuery) {
      window.Telegram.WebApp.switchInlineQuery(text);
    } else {
      TG.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`);
    }
  });

  // 7. Фикс позиции nav для Telegram Desktop.
  // Telegram рендерит свой нативный бар поверх WebView снизу,
  // из-за чего viewportHeight < innerHeight и nav уходит под бар.
  (function fixNavForTelegram() {
    const nav = document.getElementById('bottom-nav');
    if (!nav) return;

    function update() {
      const tgVH = window.Telegram?.WebApp?.viewportHeight;
      const innerH = window.innerHeight;
      if (tgVH && Math.round(tgVH) < Math.round(innerH)) {
        nav.style.bottom = (innerH - tgVH) + 'px';
      } else {
        nav.style.bottom = '0px';
      }
    }

    update();
    window.addEventListener('resize', update);
    if (window.Telegram?.WebApp) {
      window.Telegram.WebApp.onEvent('viewportChanged', update);
    }
  })();

  // 8. Онбординг → затем оффер
  setTimeout(() => Onboarding.show(), 400);
});
