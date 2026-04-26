/* ================================================
   ОФОРМЛЕНИЕ ЗАКАЗА — форма, валидация, MainButton
   ================================================ */

const Checkout = {
  /** Выбранная доставка */
  _delivery: 'cdek',
  /** Выбранная оплата */
  _payment: 'online',

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
    console.log('[checkout] _submit start, payment=', Checkout._payment);

    if (!Checkout._isValid()) {
      TG.hapticError();
      Checkout._highlightErrors();
      return;
    }

    TG.showMainButtonProgress();

    try {
      const buyerName = document.getElementById('input-name').value.trim();
      const buyerPhone = document.getElementById('input-phone').value.trim();
      const city = document.getElementById('input-city').value.trim();
      const address = document.getElementById('input-address').value.trim();
      const notes = document.getElementById('input-comment')?.value.trim() || null;

      const storeItems = Store.getItems();
      if (!storeItems || storeItems.length === 0) {
        throw new Error('Корзина пуста');
      }

      const subtotal = Store.getSubtotal();
      const discount = Store.getDiscountAmount();
      const delivery = Store.getDelivery(Checkout._delivery);
      const total = subtotal - discount + delivery;

      const products = (typeof Catalog !== 'undefined' && Array.isArray(Catalog._products)) ? Catalog._products : [];

      // Вычисляем эффективную ставку скидки из уже работающих методов Store
      const effectiveRate = subtotal > 0 ? discount / subtotal : 0;
      const orderItems = storeItems.map(item => {
        const prod = products.find(p => p.id === item.productId);
        const fullPrice = prod?.price || 1;
        const discountedPrice = effectiveRate > 0
          ? Math.round(fullPrice * (1 - effectiveRate))
          : fullPrice;
        return {
          product_id: item.productId,
          product_name: prod?.name || `#${item.productId}`,
          size: item.size,
          color: item.color,
          qty: item.qty,
          unit_price: discountedPrice,
        };
      });

      const baseOrder = {
        buyer_name: buyerName,
        buyer_phone: buyerPhone,
        city,
        address,
        notes: notes || null,
        delivery_method: Checkout._delivery,
        items: orderItems,
      };

      const deliveryLabel = Checkout._delivery === 'cdek' ? 'СДЭК' : 'Почта России';
      const itemsSummary = storeItems.map(item => {
        const prod = products.find(p => p.id === item.productId);
        return { name: prod?.name || `#${item.productId}`, size: item.size, color: item.color, qty: item.qty, price: prod?.price || 0 };
      });

      console.log('[checkout] sending order, items=', orderItems.length, 'total=', total);

      if (Checkout._payment === 'online') {
        const result = await createOrderInvoice({ ...baseOrder, payment_method: 'online' });
        console.log('[checkout] invoice received', result);
        TG.hideMainButtonProgress();

        if (!result?.invoice_link) {
          throw new Error('Сервер не вернул ссылку на оплату');
        }

        window.Telegram.WebApp.openInvoice(result.invoice_link, status => {
          if (status === 'paid') {
            Store.clear();
            Router.go('success', {
              id: result.id,
              orderNumber: result.order_number,
              items: itemsSummary,
              subtotal,
              delivery,
              deliveryMethod: deliveryLabel,
              payment: 'Онлайн',
              address: `${city}, ${address}`,
              name: buyerName,
              phone: buyerPhone,
              total,
            });
          } else if (status === 'cancelled' || status === 'failed') {
            TG.hapticError();
            window.Telegram?.WebApp?.showAlert('Оплата не прошла. Попробуйте ещё раз.');
          }
        });

      } else {
        const result = await createOrder({ ...baseOrder, payment_method: 'cod' });
        TG.hideMainButtonProgress();
        Store.clear();
        Router.go('success', {
          id: result.id,
          orderNumber: result.order_number,
          items: itemsSummary,
          subtotal,
          delivery,
          deliveryMethod: deliveryLabel,
          payment: 'При получении',
          address: `${city}, ${address}`,
          name: buyerName,
          phone: buyerPhone,
          total,
        });
      }

    } catch (err) {
      console.error('[checkout] submit error:', err);
      TG.hideMainButtonProgress();
      TG.hapticError();
      const msg = err?.message || String(err) || 'Неизвестная ошибка';
      window.Telegram?.WebApp?.showAlert(`Не удалось создать заказ: ${msg}`);
    }
  },

  /** Форматирование цены */
  _fmt(n) {
    return n.toLocaleString('ru-RU') + ' ₽';
  }
};
