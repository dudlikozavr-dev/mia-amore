/* ================================================
   STORE — состояние корзины
   Хранится в памяти + CloudStorage (если доступен)
   ================================================ */

const Store = {
  /** Массив товаров в корзине: { productId, size, color, qty } */
  _items: [],

  /** Скидка (0 или 0.1) */
  _discountRate: 0,

  /** Слушатели изменений */
  _listeners: [],

  /** Инициализация — загрузка из CloudStorage */
  init() {
    try {
      const tgStorage = window.Telegram?.WebApp?.CloudStorage;
      if (tgStorage) {
        tgStorage.getItem('cart', (err, val) => {
          if (!err && val) {
            try { Store._items = JSON.parse(val); } catch {}
            Store._notify();
          }
        });
      }
    } catch {}
  },

  /** Подписаться на изменения */
  onChange(fn) {
    Store._listeners.push(fn);
  },

  /** Уведомить всех слушателей */
  _notify() {
    Store._listeners.forEach(fn => fn(Store._items));
    Store._save();
  },

  /** Сохранить в CloudStorage */
  _save() {
    try {
      const tgStorage = window.Telegram?.WebApp?.CloudStorage;
      if (tgStorage) {
        tgStorage.setItem('cart', JSON.stringify(Store._items));
      }
    } catch {}
  },

  /** Добавить товар в корзину */
  add(productId, size, color) {
    const existing = Store._items.find(
      i => i.productId === productId && i.size === size && i.color === color
    );
    if (existing) {
      existing.qty++;
    } else {
      Store._items.push({ productId, size, color, qty: 1 });
    }
    Store._notify();
  },

  /** Изменить количество */
  setQty(index, qty) {
    if (qty <= 0) {
      Store._items.splice(index, 1);
    } else {
      Store._items[index].qty = qty;
    }
    Store._notify();
  },

  /** Удалить товар из корзины */
  remove(index) {
    Store._items.splice(index, 1);
    Store._notify();
  },

  /** Получить все товары корзины */
  getItems() {
    return Store._items;
  },

  /** Общее количество позиций */
  getCount() {
    return Store._items.reduce((sum, i) => sum + i.qty, 0);
  },

  /** Сумма товаров (до скидки) */
  getSubtotal() {
    return Store._items.reduce((sum, item) => {
      const product = PRODUCTS.find(p => p.id === item.productId);
      return sum + (product ? product.price * item.qty : 0);
    }, 0);
  },

  /** Установить скидку и сохранить в localStorage */
  setDiscount(rate) {
    Store._discountRate = rate;
    localStorage.setItem('mia_discount', String(rate));
    Store._notify();
  },

  /** Загрузить скидку из localStorage */
  loadDiscount() {
    const saved = localStorage.getItem('mia_discount');
    if (saved) Store._discountRate = parseFloat(saved) || 0;
  },

  /** Размер скидки в рублях */
  getDiscountAmount() {
    return Math.round(Store.getSubtotal() * Store._discountRate);
  },

  /** Есть ли активная скидка */
  hasDiscount() {
    return Store._discountRate > 0;
  },

  /** Стоимость доставки */
  getDelivery(method) {
    const subtotal = Store.getSubtotal();
    if (subtotal >= 3000) return 0;
    return method === 'post' ? 250 : 300;
  },

  /** Очистить корзину */
  clear() {
    Store._items = [];
    Store._notify();
  }
};
