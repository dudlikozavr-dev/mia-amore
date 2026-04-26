/**
 * api.js — клиент к бэкенду Mia-Amore.
 *
 * Все запросы идут через эти функции.
 * В заголовке X-Telegram-Init-Data передаётся подпись Telegram
 * (бэкенд проверяет HMAC-SHA256).
 */

const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://localhost:8000'
  : 'https://app.sikretsweet.ru';

/** Возвращает заголовки для запросов к API */
function _getHeaders() {
  const initData = window.Telegram?.WebApp?.initData || '';
  return {
    'Content-Type': 'application/json',
    'X-Telegram-Init-Data': initData,
  };
}

/** Базовый fetch с обработкой ошибок и таймаутом */
async function _apiRequest(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs || 30000;
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  console.log('[api]', options.method || 'GET', url);

  let res;
  try {
    res = await fetch(url, {
      ...options,
      headers: { ..._getHeaders(), ...(options.headers || {}) },
      signal: controller.signal,
    });
  } catch (e) {
    clearTimeout(timeoutId);
    if (e.name === 'AbortError') {
      throw new Error(`Таймаут запроса (${timeoutMs / 1000}s) — сервер не ответил`);
    }
    throw new Error(`Сеть: ${e.message || e.name || 'нет соединения'}`);
  }
  clearTimeout(timeoutId);

  if (!res.ok) {
    let detail = `Ошибка ${res.status}`;
    let bodyText = '';
    try {
      bodyText = await res.text();
      const body = JSON.parse(bodyText);
      if (body.detail) {
        detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      }
    } catch (_) {
      if (bodyText) detail = `${detail}: ${bodyText.slice(0, 200)}`;
    }
    console.error('[api] error response', res.status, detail);
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
 * История заказов текущего пользователя.
 * @param {number} telegramId
 */
async function fetchMyOrders(telegramId) {
  return _apiRequest(`/api/buyers/${telegramId}/orders`);
}

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

/**
 * Создаёт заказ и возвращает ссылку на Telegram Invoice (ЮКасса).
 * @param {Object} orderData — данные из формы checkout.js
 * @returns {Object} — { id, order_number, total, invoice_link }
 */
async function createOrderInvoice(orderData) {
  const user = window.Telegram?.WebApp?.initDataUnsafe?.user;

  return _apiRequest('/api/orders/invoice', {
    method: 'POST',
    body: JSON.stringify({
      buyer_telegram_id: user?.id || null,
      buyer_username: user?.username || null,
      ...orderData,
    }),
  });
}
