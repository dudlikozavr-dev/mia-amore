/* ================================================
   РОУТЕР — простой стейт-машина для навигации
   Без hash/history API — переключает CSS-классы
   ================================================ */

const Router = {
  /** Стек истории для BackButton */
  _history: ['catalog'],

  /** Текущий экран */
  current: 'catalog',

  /** Колбэки при входе на экран */
  _onEnter: {},

  /** Зарегистрировать колбэк при входе на экран */
  onEnter(screen, callback) {
    Router._onEnter[screen] = callback;
  },

  /**
   * Перейти на экран
   * @param {string} screen — id экрана без "screen-"
   * @param {*} data — данные для передачи на экран
   */
  go(screen, data) {
    if (screen === Router.current) return;

    const prev = document.getElementById('screen-' + Router.current);
    const next = document.getElementById('screen-' + screen);

    if (!next) return;

    // Анимация выхода текущего экрана
    if (prev) {
      prev.classList.remove('active');
    }

    // Показать новый экран
    next.classList.remove('slide-out-left');
    next.classList.add('active');

    // Обновить историю
    Router._history.push(screen);
    Router.current = screen;

    // Прокрутить наверх
    next.scrollTop = 0;

    // Вызвать колбэк входа на экран
    if (Router._onEnter[screen]) {
      Router._onEnter[screen](data);
    }
  },

  /**
   * Вернуться назад
   */
  back() {
    if (Router._history.length <= 1) return;

    Router._history.pop();
    const prevScreen = Router._history[Router._history.length - 1];

    const current = document.getElementById('screen-' + Router.current);
    const prev = document.getElementById('screen-' + prevScreen);

    if (current) {
      current.classList.remove('active');
    }

    if (prev) {
      prev.classList.remove('slide-out-left');
      prev.classList.add('active');
    }

    Router.current = prevScreen;

    // Вызвать колбэк входа
    if (Router._onEnter[prevScreen]) {
      Router._onEnter[prevScreen]();
    }
  },

  /**
   * Сбросить к каталогу (после заказа)
   */
  reset() {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    const catalog = document.getElementById('screen-catalog');
    catalog.classList.add('active');
    Router._history = ['catalog'];
    Router.current = 'catalog';
    if (Router._onEnter['catalog']) {
      Router._onEnter['catalog']();
    }
  }
};
