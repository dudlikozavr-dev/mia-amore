/**
 * api.js — клиент к бэкенду Mia-Amore.
 *
 * Все запросы идут через эти функции.
 * В заголовке X-Telegram-Init-Data передаётся подпись Telegram
 * (бэкенд проверяет HMAC-SHA256).
 */

const API_BASE = 'https://mia-amore-api.up.railway.app';

/** Возвращает заголовки для запросов к API */
function _getHeaders() {
  const initData = window.Telegram?.WebApp?.initData || '';
  return {
    'Content-Type': 'application/json',
    'X-Telegram-Init-Data': initData,
  };
}

/** Базовый fetch с обработкой ошибок */
async function _apiRequest(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ..._getHeaders(), ...(options.headers || {}) },
  });

  if (!res.ok) {
    let detail = `Ошибка ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch (_) {}
    throw new Error(detail);
  }

  return res.json();
}

// ─── Каталог ─────────────────────────────────────────────────────────────────

/**
 * Список товаров для каталога.
 * @param {string|null} category — slug категории (robe, pijama, ...) или null для всех
 */
async function fetchProducts(category = null) {
  const url = category && category !== 'all'
    ? `/api/products?category=${encodeURIComponent(category)}`
    : '/api/products';
  return _apiRequest(url);
}

/**
 * Полные данные товара для карточки.
 * @param {number} productId
 */
async function fetchProduct(productId) {
  return _apiRequest(`/api/products/${productId}`);
}

/** Список категорий для фильтров */
async function fetchCategories() {
  return _apiRequest('/api/categories');
}

// ─── Покупатель ───────────────────────────────────────────────────────────────

/**
 * Регистрирует/обновляет покупателя при открытии Mini App.
 * Вызывается один раз при инициализации app.js.
 */
async function identifyBuyer() {
  const user = window.Telegram?.WebApp?.initDataUnsafe?.user;
  if (!user?.id) return null;

  return _apiRequest('/api/buyers/identify', {
    method: 'POST',
    body: JSON.stringify({
      telegram_id: user.id,
      first_name: user.first_name || null,
      last_name: user.last_name || null,
      username: user.username || null,
    }),
  });
}

// ─── Заказ ────────────────────────────────────────────────────────────────────

/**
 * Оформляет заказ.
 * @param {Object} orderData — данные из формы checkout.js
 * @returns {Object} — { id, order_number, total, status }
 */
async function createOrder(orderData) {
  const user = window.Telegram?.WebApp?.initDataUnsafe?.user;

  return _apiRequest('/api/orders', {
    method: 'POST',
    body: JSON.stringify({
      buyer_telegram_id: user?.id || null,
      buyer_username: user?.username || null,
      ...orderData,
    }),
  });
}
