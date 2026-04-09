/* ================================================
   ОФОРМЛЕНИЕ ЗАКАЗА — форма, валидация, MainButton
   ================================================ */

const Checkout = {
  /** Выбранная доставка */
  _delivery: 'cdek',
  /** Выбранная оплата */
  _payment: 'cod',

  /** Инициализация */
  init() {
    // Выбор доставки
    document.getElementById('delivery-options').addEventListener('click', e => {
      const card = e.target.closest('.option-card');
      if (!card) return;
      TG.hapticSelection();
      document.querySelectorAll('#delivery-options .option-card').forEach(c => c.classList.remove('option-card--active'));
      card.classList.add('option-card--active');
      Checkout._delivery = card.dataset.delivery;
      Checkout._updateTotal();
    });

    // Выбор оплаты
    document.getElementById('payment-options').addEventListener('click', e => {
      const card = e.target.closest('.option-card');
      if (!card) return;
      TG.hapticSelection();
      document.querySelectorAll('#payment-options .option-card').forEach(c => c.classList.remove('option-card--active'));
      card.classList.add('option-card--active');
      Checkout._payment = card.dataset.payment;
    });

    // Валидация при вводе
    ['input-name', 'input-phone', 'input-city', 'input-address'].forEach(id => {
      document.getElementById(id).addEventListener('input', () => {
        document.getElementById(id).classList.remove('input--error');
        Checkout._checkForm();
      });
    });
  },

  /** Показать экран оформления */
  show() {
    TG.showBackButton(() => Router.back());

    // Автозаполнение из Telegram
    const user = TG.getUser();
    const nameInput = document.getElementById('input-name');
    if (user && !nameInput.value) {
      nameInput.value = [user.first_name, user.last_name].filter(Boolean).join(' ');
    }

    Checkout._updateTotal();
    Checkout._checkForm();
  },

  /** Обновить итого */
  _updateTotal() {
    const subtotal = Store.getSubtotal();
    const discount = Store.getDiscountAmount();
    const delivery = Store.getDelivery(Checkout._delivery);
    const total = subtotal - discount + delivery;

    document.getElementById('checkout-items-total').textContent = Checkout._fmt(subtotal);
    document.getElementById('checkout-delivery').textContent = delivery === 0 ? 'Бесплатно' : Checkout._fmt(delivery);
    document.getElementById('checkout-grand-total').textContent = Checkout._fmt(total);

    // Строка скидки
    const discountRow = document.getElementById('checkout-discount-row');
    if (Store.hasDiscount() && discount > 0) {
      document.getElementById('checkout-discount').textContent = `−${Checkout._fmt(discount)}`;
      discountRow.hidden = false;
    } else {
      discountRow.hidden = true;
    }

    // Обновить MainButton
    TG.showMainButton(`Оплатить ${Checkout._fmt(total)}`, () => Checkout._submit());
  },

  /** Проверить заполненность формы */
  _checkForm() {
    const valid = Checkout._isValid();
    if (valid) {
      const total = Store.getSubtotal() - Store.getDiscountAmount() + Store.getDelivery(Checkout._delivery);
      TG.enableMainButton(`Оплатить ${Checkout._fmt(total)}`);
    } else {
      TG.disableMainButton('Заполните форму');
    }
  },

  /** Валидация полей */
  _isValid() {
    const name = document.getElementById('input-name').value.trim();
    const phone = document.getElementById('input-phone').value.trim();
    const city = document.getElementById('input-city').value.trim();
    const address = document.getElementById('input-address').value.trim();
    return name && phone && city && address;
  },

  /** Подсветить пустые поля */
  _highlightErrors() {
    ['input-name', 'input-phone', 'input-city', 'input-address'].forEach(id => {
      const el = document.getElementById(id);
      if (!el.value.trim()) {
        el.classList.add('input--error');
      }
    });
  },

  /** Отправка заказа */
  async _submit() {
    if (!Checkout._isValid()) {
      TG.hapticError();
      Checkout._highlightErrors();
      return;
    }

    TG.showMainButtonProgress();

    // Имитация отправки на сервер (1 секунда)
    await new Promise(r => setTimeout(r, 1000));

    TG.hideMainButtonProgress();

    // Собираем данные заказа
    const order = {
      id: Math.floor(1000 + Math.random() * 9000),
      items: Store.getItems().map(item => {
        const p = PRODUCTS.find(prod => prod.id === item.productId);
        return {
          name: p?.name || 'Товар',
          size: item.size,
          color: item.color,
          qty: item.qty,
          price: p?.price || 0
        };
      }),
      subtotal: Store.getSubtotal(),
      delivery: Store.getDelivery(Checkout._delivery),
      deliveryMethod: Checkout._delivery === 'cdek' ? 'СДЭК' : 'Почта России',
      payment: Checkout._payment === 'cod' ? 'При получении' : 'Онлайн',
      address: `${document.getElementById('input-city').value}, ${document.getElementById('input-address').value}`,
      name: document.getElementById('input-name').value,
      phone: document.getElementById('input-phone').value
    };

    // Очистить корзину
    Store.clear();

    // Перейти к экрану успеха
    Router.go('success', order);
  },

  /** Форматирование цены */
  _fmt(n) {
    return n.toLocaleString('ru-RU') + ' ₽';
  }
};
