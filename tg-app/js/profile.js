/* ================================================
   ПРОФИЛЬ — информация о пользователе
   ================================================ */

const Profile = {
  STORAGE_KEY: 'mia_pref_size',

  /** Инициализация */
  init() {
    // Поддержка
    document.getElementById('btn-profile-support')?.addEventListener('click', () => {
      TG.hapticLight();
      TG.openTelegramLink('https://t.me/sikretsweet_home_bot');
    });

    // Поделиться
    document.getElementById('btn-profile-share')?.addEventListener('click', () => {
      TG.hapticLight();
      const text = 'Смотри, нашла классный магазин шёлковой домашней одежды 🌸';
      const url = 'https://t.me/sikretsweet_home_bot/app';
      if (window.Telegram?.WebApp?.switchInlineQuery) {
        window.Telegram.WebApp.switchInlineQuery(text);
      } else {
        TG.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`);
      }
    });

    // Выбор размера
    document.querySelectorAll('.profile-size-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        TG.hapticSelection();
        document.querySelectorAll('.profile-size-chip').forEach(c => c.classList.remove('size-chip--active'));
        chip.classList.add('size-chip--active');
        localStorage.setItem(Profile.STORAGE_KEY, chip.dataset.size);
      });
    });
  },

  /** Заполнить экран данными и показать */
  show() {
    // Имя пользователя из Telegram
    const user = TG.getUser();
    const nameEl = document.getElementById('profile-name');
    const subEl = document.getElementById('profile-username');
    if (user && nameEl) {
      nameEl.textContent = [user.first_name, user.last_name].filter(Boolean).join(' ') || 'Гостья';
      subEl.textContent = user.username ? `@${user.username}` : 'Добро пожаловать!';
    }

    // Восстановить сохранённый размер
    const savedSize = localStorage.getItem(Profile.STORAGE_KEY);
    document.querySelectorAll('.profile-size-chip').forEach(c => {
      c.classList.toggle('size-chip--active', c.dataset.size === savedSize);
    });

    // Статус скидки
    const discountRow = document.getElementById('profile-discount-row');
    if (discountRow) discountRow.hidden = !localStorage.getItem('mia_discount');
  }
};
