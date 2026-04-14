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

    // История заказов
    if (user?.id) {
      Profile._loadOrders(user.id);
    } else {
      document.getElementById('profile-orders-loading').textContent = 'Войдите через Telegram для просмотра заказов';
    }
  },

  /** Загрузить и отрисовать заказы */
  async _loadOrders(telegramId) {
    const list = document.getElementById('profile-orders-list');
    const loading = document.getElementById('profile-orders-loading');
    loading.textContent = 'Загрузка...';
    loading.hidden = false;

    try {
      const orders = await fetchMyOrders(telegramId);
      loading.hidden = true;

      if (!orders.length) {
        list.innerHTML = '<p class="profile-orders-empty">Заказов пока нет</p>';
        return;
      }

      list.innerHTML = orders.map(o => Profile._orderHTML(o)).join('');
    } catch (e) {
      loading.textContent = 'Не удалось загрузить заказы';
    }
  },

  /** HTML одного заказа */
  _orderHTML(o) {
    const STATUS_LABEL = {
      new: 'Новый',
      confirmed: 'Подтверждён',
      shipped: 'Отправлен',
      delivered: 'Доставлен',
      cancelled: 'Отменён',
    };
    const STATUS_COLOR = {
      new: 'var(--accent)',
      confirmed: '#4CAF50',
      shipped: '#2196F3',
      delivered: '#4CAF50',
      cancelled: 'var(--hint)',
    };

    const label = STATUS_LABEL[o.status] || o.status;
    const color = STATUS_COLOR[o.status] || 'var(--hint)';
    const date = new Date(o.created_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
    const total = o.total.toLocaleString('ru-RU') + ' ₽';
    const firstItem = o.items[0];
    const moreCount = o.items.length - 1;

    return `
      <div class="profile-order-card">
        <div class="profile-order-header">
          <span class="profile-order-number">${o.order_number}</span>
          <span class="profile-order-status" style="color:${color}">${label}</span>
        </div>
        <div class="profile-order-item">${firstItem.product_name}${firstItem.size ? `, ${firstItem.size}` : ''}${moreCount > 0 ? ` <span class="profile-order-more">+${moreCount} ещё</span>` : ''}</div>
        <div class="profile-order-footer">
          <span class="profile-order-date">${date}</span>
          <span class="profile-order-total">${total}</span>
        </div>
      </div>
    `;
  }
};
