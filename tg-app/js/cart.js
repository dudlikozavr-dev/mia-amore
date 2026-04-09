/* ================================================
   КОРЗИНА — список товаров, +/−, итого
   ================================================ */

const Cart = {
  /** Текущий способ доставки для расчёта */
  _deliveryMethod: 'cdek',

  /** Инициализация */
  init() {
    // Кнопка «Перейти в каталог» из пустой корзины
    document.getElementById('btn-to-catalog').addEventListener('click', () => {
      Router.go('catalog');
    });
  },

  /** Показать экран корзины */
  show() {
    TG.showBackButton(() => Router.back());
    Cart.render();
  },

  /** Рендер корзины */
  render() {
    const items = Store.getItems();
    const container = document.getElementById('cart-items');
    const emptyEl = document.getElementById('cart-empty');
    const summaryEl = document.getElementById('cart-summary');

    if (items.length === 0) {
      container.innerHTML = '';
      emptyEl.hidden = false;
      summaryEl.hidden = true;
      TG.hideMainButton();
      return;
    }

    emptyEl.hidden = true;
    summaryEl.hidden = false;

    // Рендер карточек
    container.innerHTML = items.map((item, idx) => {
      const p = PRODUCTS.find(prod => prod.id === item.productId);
      if (!p) return '';
      return `
        <div class="cart-item" data-idx="${idx}">
          <img class="cart-item__img" src="${p.images[0]}" alt="${p.name}" loading="lazy">
          <div class="cart-item__info">
            <div class="cart-item__name">${p.name}</div>
            <div class="cart-item__variant">Размер ${item.size}, ${item.color}</div>
            <div class="cart-item__price">${Cart._fmt(p.price * item.qty)}</div>
          </div>
          <div class="cart-item__actions">
            <button class="cart-item__qty-btn" data-action="minus" data-idx="${idx}">−</button>
            <span class="cart-item__qty">${item.qty}</span>
            <button class="cart-item__qty-btn" data-action="plus" data-idx="${idx}">+</button>
            <button class="cart-item__delete" data-action="delete" data-idx="${idx}">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>
      `;
    }).join('');

    // Обработчики кнопок
    container.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const idx = parseInt(btn.dataset.idx);
        const action = btn.dataset.action;
        const currentItem = Store.getItems()[idx];

        if (action === 'plus') {
          TG.hapticLight();
          Store.setQty(idx, currentItem.qty + 1);
          Cart.render();
        } else if (action === 'minus') {
          if (currentItem.qty === 1) {
            const ok = await TG.confirm('Удалить товар из корзины?');
            if (ok) {
              Store.remove(idx);
              Cart.render();
            }
          } else {
            TG.hapticLight();
            Store.setQty(idx, currentItem.qty - 1);
            Cart.render();
          }
        } else if (action === 'delete') {
          const ok = await TG.confirm('Удалить товар из корзины?');
          if (ok) {
            Store.remove(idx);
            Cart.render();
          }
        }
      });
    });

    // Итого
    Cart._updateSummary();

    // MainButton
    const total = Store.getSubtotal() - Store.getDiscountAmount() + Store.getDelivery(Cart._deliveryMethod);
    TG.showMainButton(`Оформить заказ — ${Cart._fmt(total)}`, () => {
      Router.go('checkout');
    });
  },

  /** Обновить блок «Итого» */
  _updateSummary() {
    const count = Store.getCount();
    const subtotal = Store.getSubtotal();
    const discount = Store.getDiscountAmount();
    const delivery = Store.getDelivery(Cart._deliveryMethod);
    const total = subtotal - discount + delivery;

    document.getElementById('cart-items-count').textContent = `Товары (${count} шт.)`;
    document.getElementById('cart-items-total').textContent = Cart._fmt(subtotal);
    document.getElementById('cart-delivery').textContent = delivery === 0 ? 'Бесплатно' : Cart._fmt(delivery);
    document.getElementById('cart-total').textContent = Cart._fmt(total);

    // Строка скидки
    const discountRow = document.getElementById('cart-discount-row');
    if (Store.hasDiscount() && discount > 0) {
      document.getElementById('cart-discount').textContent = `−${Cart._fmt(discount)}`;
      discountRow.hidden = false;
    } else {
      discountRow.hidden = true;
    }

    // Подсказка о бесплатной доставке
    const hint = document.getElementById('cart-free-delivery-hint');
    if (subtotal < 3000 && subtotal > 0) {
      const remaining = 3000 - subtotal;
      hint.textContent = `Добавьте ещё на ${Cart._fmt(remaining)} — доставка бесплатно`;
      hint.hidden = false;
    } else {
      hint.hidden = true;
    }
  },

  /** Форматирование цены */
  _fmt(n) {
    return n.toLocaleString('ru-RU') + ' ₽';
  }
};
