# Telegram Mini App — магазин домашней одежды

## Структура проекта

```
tg-app/
├── index.html           ← Точка входа. Все 5 экранов + bottom sheet
├── css/
│   ├── theme.css        ← Переменные из Telegram themeParams (dark/light)
│   ├── base.css         ← Reset, типографика, экраны, шапка, кнопки
│   └── components.css   ← Фильтры, карточки, галерея, корзина, форма, sheet
├── js/
│   ├── data.js          ← Каталог товаров (массив PRODUCTS). Менять данные тут
│   ├── telegram.js      ← Обёртки над Telegram WebApp API
│   ├── router.js        ← Навигация между экранами (стейт-машина)
│   ├── store.js         ← Корзина (состояние + CloudStorage)
│   ├── catalog.js       ← Экран каталога: сетка, фильтры
│   ├── product.js       ← Экран товара: галерея, размеры, MainButton
│   ├── cart.js          ← Экран корзины: список, +/−, итого
│   ├── checkout.js      ← Экран оформления: форма, валидация
│   ├── success.js       ← Экран подтверждения заказа
│   └── app.js           ← Инициализация всех модулей + BottomSheet
└── img/                 ← Папка для фото товаров (WebP, 600×800)
```

## Навигация между экранами

```
Каталог → (тап карточка) → Карточка товара
Каталог → (тап корзина)  → Корзина
Карточка товара → (BackButton) → Каталог
Карточка товара → (MainButton «В корзину») → остаётся, товар добавлен
Корзина → (BackButton) → Каталог
Корзина → (MainButton «Оформить») → Оформление
Оформление → (BackButton) → Корзина
Оформление → (MainButton «Оплатить») → Подтверждение
Подтверждение → (кнопка «В каталог») → Каталог (reset)
```

## Где менять данные

### Товары
Файл: `js/data.js` — массив `PRODUCTS`

Каждый товар:
```js
{
  id: число,
  name: 'Название',
  category: 'kimono' | 'pijama' | 'set',
  material: 'silk' | 'cotton' | 'velour',
  materialLabel: 'Текст для карточки',
  price: число,
  oldPrice: число | null,
  badge: 'hit' | 'new' | null,
  stock: число,
  sizes: ['XS', 'S', 'M', 'L', 'XL'],
  disabledSizes: ['XL'],     // Размеры, которых нет
  colors: [
    { name: 'Бежевый', hex: '#D4B896' }
  ],
  images: ['url1', 'url2'],  // 3-4 фото, формат 3:4
  description: 'Текст',
  care: 'Инструкция по уходу'
}
```

### Фильтры
Файл: `index.html` — секция `#filters`
Атрибут `data-filter` должен совпадать с `category` или `material` в данных.

### Таблица размеров
Файл: `index.html` — секция `#sheet-sizes`

### Стоимость доставки
Файл: `js/store.js` — метод `getDelivery()`
- Бесплатно от 3000 ₽
- СДЭК: 300 ₽
- Почта России: 250 ₽

## Telegram API использование

| API | Где | Зачем |
|---|---|---|
| `WebApp.expand()` | app.js | Полный экран при запуске |
| `MainButton` | product.js, cart.js, checkout.js | Основной CTA |
| `BackButton` | product.js, cart.js, checkout.js | Навигация назад |
| `HapticFeedback` | Все экраны | Тактильная отдача |
| `CloudStorage` | store.js | Сохранение корзины |
| `showConfirm()` | cart.js | Подтверждение удаления |
| `initDataUnsafe.user` | checkout.js | Автозаполнение имени |

## Как запустить

1. Разместить `tg-app/` на хостинге с HTTPS (Vercel, Netlify, GitHub Pages)
2. В @BotFather: Bot Settings → Menu Button → настроить URL на `https://ваш-домен/tg-app/`
3. Открыть бота в Telegram → нажать кнопку меню

Для локальной разработки:
```bash
cd tg-app
npx serve .
# или
python -m http.server 8080
```

## Фото товаров

Сейчас используются SVG-заглушки (функция `placeholder()` в data.js).
Для замены на реальные фото:
1. Положить файлы в `tg-app/img/` (формат WebP, 600×800px)
2. В data.js заменить вызовы `placeholder(...)` на пути: `'img/sakura-1.webp'`
