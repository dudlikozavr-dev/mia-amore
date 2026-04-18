/* ================================================
   КАРТОЧКА ТОВАРА — галерея, размеры, MainButton
   ================================================ */

/** Измерения по размерам (стандарт Mia-Amore) */
const SIZE_CHART = {
  XS:  { chest: '82–86',  waist: '60–64', hips: '88–92'  },
  S:   { chest: '86–90',  waist: '64–68', hips: '92–96'  },
  M:   { chest: '90–94',  waist: '68–72', hips: '96–100' },
  L:   { chest: '94–100', waist: '72–78', hips: '100–106'},
  XL:  { chest: '100–106',waist: '78–84', hips: '106–112'},
  XXL: { chest: '106–112',waist: '84–90', hips: '112–118'},
};

const Product = {
  /** Текущий товар */
  _product: null,
  /** Выбранный размер */
  _size: null,
  /** Выбранный цвет (индекс) */
  _colorIdx: 0,
  /** Текущий слайд галереи */
  _slide: 0,
  /** Координаты для свайпа */
  _touchStartX: 0,

  /** Инициализация обработчиков */
  init() {
    // Кнопка назад поверх галереи
    document.getElementById('btn-product-back').addEventListener('click', () => {
      TG.hapticSelection();
      Router.back();
    });

    // Таблица размеров
    document.getElementById('btn-size-chart').addEventListener('click', () => {
      Product._renderSizeChart();
      BottomSheet.open('sheet-sizes');
    });

    // Кнопка «Написать в чат» в таблице размеров
    document.getElementById('btn-chat-size').addEventListener('click', () => {
      TG.close();
    });

    // Сворачиваемое описание
    document.getElementById('btn-desc-toggle').addEventListener('click', () => {
      const desc = document.getElementById('product-desc');
      const btn = document.getElementById('btn-desc-toggle');
      const care = document.getElementById('product-care');
      desc.classList.toggle('expanded');
      if (desc.classList.contains('expanded')) {
        btn.textContent = 'Свернуть';
        care.hidden = false;
      } else {
        btn.textContent = 'Подробнее';
        care.hidden = true;
      }
    });

    // Свайп галереи
    const gallery = document.getElementById('product-gallery');
    gallery.addEventListener('touchstart', e => {
      Product._touchStartX = e.touches[0].clientX;
    }, { passive: true });

    gallery.addEventListener('touchend', e => {
      const diff = Product._touchStartX - e.changedTouches[0].clientX;
      if (Math.abs(diff) > 50) {
        if (diff > 0) Product._nextSlide();
        else Product._prevSlide();
      }
    }, { passive: true });
  },

  /** Показать экран товара */
  async show(productId) {
    Product._size = null;
    Product._colorIdx = 0;
    Product._slide = 0;

    // Показываем экран сразу, данные подгружаем
    document.getElementById('product-name').textContent = 'Загрузка...';
    document.getElementById('product-price').textContent = '';
    TG.showBackButton(() => Router.back());
    TG.disableMainButton('Выберите размер');
    TG.showMainButton('Выберите размер', () => Product._addToCart());

    let p;
    try {
      p = await fetchProduct(productId);
    } catch (e) {
      document.getElementById('product-name').textContent = 'Ошибка загрузки';
      return;
    }

    // Нормализуем поля API → формат компонента
    p.oldPrice    = p.old_price;
    p.materialLabel = p.material_label;
    p.sizeStock = p.size_stock || {};
    // Если задан size_stock — он единственный источник правды по недоступным размерам
    const fromStock = Object.keys(p.sizeStock).length
      ? p.sizes.filter(s => (p.sizeStock[s] ?? 0) <= 0)
      : null;
    p.disabledSizes = fromStock ?? (p.disabled_sizes || []);
    // images из API: [{id, url, sort_order, image_type}] → только галерея
    p.imageUrls = (p.images || [])
      .filter(img => img.image_type !== 'size_chart')
      .map(img => img.url);
    // size_chart_url уже приходит из API

    Product._product = p;

    // Заполнить данные
    document.getElementById('product-name').textContent = p.name;
    document.getElementById('product-price').textContent = Product._fmt(p.price);

    const oldPrice = document.getElementById('product-old-price');
    if (p.oldPrice) {
      oldPrice.textContent = Product._fmt(p.oldPrice);
      oldPrice.hidden = false;
    } else {
      oldPrice.hidden = true;
    }

    document.getElementById('product-material').textContent = p.materialLabel || '';

    // Остаток
    const stock = document.getElementById('product-stock');
    if (p.stock <= 3) {
      stock.textContent = `Осталось ${p.stock} шт.`;
      stock.hidden = false;
    } else {
      stock.hidden = true;
    }

    // Галерея
    Product._renderGallery(p);

    // Размеры
    Product._renderSizes(p);

    // Цвета
    Product._renderColors(p);

    // Описание
    const desc = document.getElementById('product-desc');
    desc.textContent = p.description || '';
    desc.classList.remove('expanded');
    document.getElementById('btn-desc-toggle').textContent = 'Подробнее';
    document.getElementById('btn-desc-toggle').hidden = false;

    const care = document.getElementById('product-care');
    care.textContent = p.care || '';
    care.hidden = true;

    // Telegram: BackButton + MainButton
    TG.showBackButton(() => Router.back());
    TG.disableMainButton('Выберите размер');
    TG.showMainButton('Выберите размер', () => Product._addToCart());
  },

  /** Отрисовка галереи */
  _renderGallery(p) {
    const track = document.getElementById('gallery-track');
    const dots = document.getElementById('gallery-dots');

    track.innerHTML = p.imageUrls.map(src =>
      `<div class="gallery__slide"><img src="${src}" alt="${p.name}"></div>`
    ).join('');

    dots.innerHTML = p.imageUrls.map((_, i) =>
      `<div class="gallery__dot ${i === 0 ? 'gallery__dot--active' : ''}"></div>`
    ).join('');

    track.style.transform = 'translateX(0)';
    Product._slide = 0;
  },

  /** Переход к следующему слайду */
  _nextSlide() {
    const total = Product._product.imageUrls.length;
    if (Product._slide < total - 1) {
      Product._slide++;
      Product._updateSlide();
    }
  },

  /** Переход к предыдущему слайду */
  _prevSlide() {
    if (Product._slide > 0) {
      Product._slide--;
      Product._updateSlide();
    }
  },

  /** Обновить позицию слайда */
  _updateSlide() {
    const track = document.getElementById('gallery-track');
    track.style.transform = `translateX(-${Product._slide * 100}%)`;

    document.querySelectorAll('#gallery-dots .gallery__dot').forEach((dot, i) => {
      dot.classList.toggle('gallery__dot--active', i === Product._slide);
    });
  },

  /** Отрисовка чипов размера */
  _renderSizes(p) {
    const container = document.getElementById('size-chips');
    container.innerHTML = p.sizes.map(size => {
      const disabled = p.disabledSizes.includes(size) ? ' size-chip--disabled' : '';
      return `<button class="size-chip${disabled}" data-size="${size}">${size}</button>`;
    }).join('');

    container.querySelectorAll('.size-chip:not(.size-chip--disabled)').forEach(btn => {
      btn.addEventListener('click', () => {
        TG.hapticSelection();
        container.querySelectorAll('.size-chip').forEach(c => c.classList.remove('size-chip--active'));
        btn.classList.add('size-chip--active');
        Product._size = btn.dataset.size;
        TG.enableMainButton(`В корзину — ${Product._fmt(Product._product.price)}`);
      });
    });
  },

  /** Отрисовка свотчей цвета */
  _renderColors(p) {
    const section = document.getElementById('color-section');
    const container = document.getElementById('color-swatches');
    const label = document.getElementById('color-name');

    if (p.colors.length <= 1) {
      section.hidden = true;
      return;
    }

    section.hidden = false;
    label.textContent = p.colors[0].name;

    container.innerHTML = p.colors.map((c, i) =>
      `<div class="color-swatch ${i === 0 ? 'color-swatch--active' : ''}"
            style="background:${c.hex}" data-idx="${i}" title="${c.name}"></div>`
    ).join('');

    container.querySelectorAll('.color-swatch').forEach(swatch => {
      swatch.addEventListener('click', () => {
        TG.hapticSelection();
        container.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('color-swatch--active'));
        swatch.classList.add('color-swatch--active');
        Product._colorIdx = parseInt(swatch.dataset.idx);
        label.textContent = p.colors[Product._colorIdx].name;
      });
    });
  },

  /** Добавить в корзину */
  _addToCart() {
    if (!Product._size) {
      TG.hapticError();
      return;
    }

    const p = Product._product;
    const color = p.colors[Product._colorIdx].name;
    Store.add(p.id, Product._size, color);

    TG.hapticSuccess();

    // Анимация кнопки «Добавлено»
    TG.disableMainButton('Добавлено ✓');
    setTimeout(() => {
      TG.enableMainButton(`В корзину — ${Product._fmt(p.price)}`);
    }, 1500);
  },

  /** Заполнить таблицу размеров данными текущего товара */
  _renderSizeChart() {
    const p = Product._product;
    if (!p) return;

    const imgWrap = document.getElementById('size-chart-img-wrap');
    const img = document.getElementById('size-chart-img');
    const table = document.getElementById('size-chart-table');

    if (p.size_chart_url) {
      // Показываем картинку из карточки товара
      img.src = p.size_chart_url;
      imgWrap.hidden = false;
      table.hidden = true;
    } else {
      // Fallback: текстовая таблица с размерами из карточки
      imgWrap.hidden = true;
      table.hidden = false;

      const tbody = document.getElementById('size-table-body');
      tbody.innerHTML = p.sizes.map(size => {
        const m = SIZE_CHART[size];
        const disabled = p.disabledSizes.includes(size);
        const cls = disabled ? ' class="size-table__row--disabled"' : '';
        const chest = m ? m.chest : '—';
        const waist = m ? m.waist : '—';
        const hips  = m ? m.hips  : '—';
        return `<tr${cls}><td>${size}${disabled ? ' <span class="size-table__sold-out">нет</span>' : ''}</td><td>${chest}</td><td>${waist}</td><td>${hips}</td></tr>`;
      }).join('');
    }
  },

  /** Форматирование цены */
  _fmt(n) {
    return n.toLocaleString('ru-RU') + ' ₽';
  }
};
