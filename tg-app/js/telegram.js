/* ================================================
   TELEGRAM — обёртки над WebApp API
   Безопасные вызовы: работает и вне Telegram (в браузере)
   ================================================ */

const tg = window.Telegram?.WebApp;

const TG = {
  /** Инициализация: полный экран + сигнал готовности */
  init() {
    if (!tg) return;
    tg.ready();
    tg.expand();
  },

  /** Получить данные пользователя */
  getUser() {
    return tg?.initDataUnsafe?.user || null;
  },

  /* --- MainButton --- */

  showMainButton(text, callback) {
    if (!tg) return;
    tg.MainButton.setText(text);
    tg.MainButton.show();
    tg.MainButton.enable();
    // Убираем старый обработчик и ставим новый
    tg.MainButton.offClick(TG._mainBtnCb);
    TG._mainBtnCb = callback;
    tg.MainButton.onClick(callback);
  },

  disableMainButton(text) {
    if (!tg) return;
    if (text) tg.MainButton.setText(text);
    tg.MainButton.disable();
  },

  enableMainButton(text) {
    if (!tg) return;
    if (text) tg.MainButton.setText(text);
    tg.MainButton.enable();
  },

  hideMainButton() {
    if (!tg) return;
    tg.MainButton.hide();
    tg.MainButton.offClick(TG._mainBtnCb);
  },

  showMainButtonProgress() {
    if (!tg) return;
    tg.MainButton.showProgress(false);
  },

  hideMainButtonProgress() {
    if (!tg) return;
    tg.MainButton.hideProgress();
  },

  _mainBtnCb: null,

  /* --- BackButton --- */

  showBackButton(callback) {
    if (!tg) return;
    tg.BackButton.show();
    tg.BackButton.offClick(TG._backBtnCb);
    TG._backBtnCb = callback;
    tg.BackButton.onClick(callback);
  },

  hideBackButton() {
    if (!tg) return;
    tg.BackButton.hide();
    tg.BackButton.offClick(TG._backBtnCb);
  },

  _backBtnCb: null,

  /* --- HapticFeedback --- */

  hapticLight() {
    tg?.HapticFeedback?.impactOccurred('light');
  },

  hapticSuccess() {
    tg?.HapticFeedback?.notificationOccurred('success');
  },

  hapticError() {
    tg?.HapticFeedback?.notificationOccurred('error');
  },

  hapticSelection() {
    tg?.HapticFeedback?.selectionChanged();
  },

  /* --- Диалоги --- */

  confirm(message) {
    return new Promise(resolve => {
      if (tg?.showConfirm) {
        tg.showConfirm(message, resolve);
      } else {
        resolve(window.confirm(message));
      }
    });
  },

  /** Открыть ссылку Telegram (t.me/...) внутри приложения */
  openTelegramLink(url) {
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(url);
    } else {
      window.open(url, '_blank');
    }
  },

  /** Закрыть Mini App */
  close() {
    tg?.close();
  },

  /** Запросить контакт */
  requestContact() {
    return new Promise(resolve => {
      if (tg?.requestContact) {
        tg.requestContact(resolve);
      } else {
        resolve(null);
      }
    });
  }
};
