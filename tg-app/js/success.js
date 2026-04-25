/* ================================================
   ПОДТВЕРЖДЕНИЕ ЗАКАЗА — итоговый экран
   ================================================ */

const Success = {
  /** Инициализация */
  init() {
    document.getElementById('btn-back-catalog').addEventListener('click', () => {
      Router.reset();
    });
  },

  /** Показать экран с данными заказа */
  show(order) {
    if (!order) return;

    TG.hideMainButton();
    TG.hideBackButton();
    TG.hapticSuccess();

    // Номер заказа
    document.getElementById('success-order-id').textContent = `Заказ ${order.orderNumber || ('#' + order.id)}`;

    // Сводка
    const summary = document.getElementById('success-summary');
    let html = '';

    order.items.forEach(item => {
      html += `<div class="success__summary-item">
        ${item.name} — ${item.size}, ${item.color} × ${item.qty}
      </div>`;
    });

    html += `<div class="success__summary-item" style="color:var(--hint); margin-top:8px">
      Доставка: ${order.deliveryMethod}
    </div>`;
    html += `<div class="success__summary-item" style="color:var(--hint)">
      Оплата: ${order.payment}
    </div>`;
    html += `<div class="success__summary-item" style="color:var(--hint)">
      Адрес: ${order.address}
    </div>`;

    const total = order.total ?? (order.subtotal + order.delivery);
    html += `<div class="success__summary-total">Итого: ${total.toLocaleString('ru-RU')} ₽</div>`;

    summary.innerHTML = html;
  }
};
