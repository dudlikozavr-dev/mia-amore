/* ================================================
   КАТАЛОГ ТОВАРОВ — Mia-Amore
   Бренд шёлковой домашней одежды для женщин
   Для добавления/изменения товара — редактируй этот файл
   ================================================ */

/**
 * Фото-заглушки: генерируются SVG нужного цвета
 * При замене на реальные фото — используй WebP, размер 3:4
 * Рекомендуемый размер: 600x800px
 */
function placeholder(color, text) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800" viewBox="0 0 600 800">
    <rect fill="${color}" width="600" height="800"/>
    <text fill="rgba(255,255,255,0.5)" font-family="sans-serif" font-size="18" font-weight="400"
          text-anchor="middle" x="300" y="370">Mia-Amore</text>
    <text fill="rgba(255,255,255,0.6)" font-family="sans-serif" font-size="24" font-weight="600"
          text-anchor="middle" x="300" y="405">${text}</text>
    <text fill="rgba(255,255,255,0.3)" font-family="sans-serif" font-size="14"
          text-anchor="middle" x="300" y="435">фото 600×800</text>
  </svg>`;
  return 'data:image/svg+xml,' + encodeURIComponent(svg);
}

const PRODUCTS = [
  {
    id: 1,
    name: 'Халат «Bella»',
    category: 'robe',
    material: 'silk',
    materialLabel: 'Шёлк натуральный',
    price: 8990,
    oldPrice: 10990,
    badge: 'hit',
    stock: 6,
    sizes: ['XS', 'S', 'M', 'L', 'XL'],
    disabledSizes: [],
    colors: [
      { name: 'Чёрный', hex: '#1C1C1E' },
      { name: 'Бордо', hex: '#6B2D3E' },
      { name: 'Шампань', hex: '#E8DCC8' }
    ],
    images: [
      placeholder('#1C1C1E', '«Bella» — чёрный'),
      placeholder('#2C2C2E', '«Bella» — детали'),
      placeholder('#3C3C3E', '«Bella» — спина')
    ],
    description: 'Длинный халат-кимоно из натурального шёлка с поясом. Широкие рукава, глубокий запах. Роскошный блеск и невесомость — идеален для утреннего ритуала.',
    care: 'Ручная стирка при 30°. Не отжимать. Гладить с изнанки через ткань на минимальной температуре.'
  },
  {
    id: 2,
    name: 'Халат «Rosalia»',
    category: 'robe',
    material: 'satin',
    materialLabel: 'Шёлковый сатин',
    price: 5990,
    oldPrice: null,
    badge: null,
    stock: 12,
    sizes: ['XS', 'S', 'M', 'L', 'XL'],
    disabledSizes: ['XL'],
    colors: [
      { name: 'Пудровый', hex: '#E8C8C0' },
      { name: 'Жемчужный', hex: '#F0EDE8' }
    ],
    images: [
      placeholder('#E8C8C0', '«Rosalia» — пудра'),
      placeholder('#D8B8B0', '«Rosalia» — детали'),
      placeholder('#F0E0D8', '«Rosalia» — пояс')
    ],
    description: 'Короткий халат из шёлкового сатина с кружевной отделкой по рукавам и подолу. Мягкий пояс в тон. Длина до середины бедра.',
    care: 'Ручная стирка при 30°. Не использовать отбеливатель. Гладить при низкой температуре.'
  },
  {
    id: 3,
    name: 'Пижама «Olivia»',
    category: 'pijama',
    material: 'silk',
    materialLabel: 'Шёлк 100%, 19 momme',
    price: 7490,
    oldPrice: 8990,
    badge: 'new',
    stock: 8,
    sizes: ['S', 'M', 'L', 'XL'],
    disabledSizes: [],
    colors: [
      { name: 'Графит', hex: '#4A4A4E' },
      { name: 'Слоновая кость', hex: '#F5F0E8' }
    ],
    images: [
      placeholder('#4A4A4E', '«Olivia» — графит'),
      placeholder('#5A5A5E', '«Olivia» — рубашка'),
      placeholder('#3A3A3E', '«Olivia» — брюки')
    ],
    description: 'Классическая пижама: рубашка с отложным воротником и перламутровыми пуговицами + брюки на мягкой резинке. Плотность шёлка 19 momme — не просвечивает.',
    care: 'Ручная стирка при 30°. Гладить с изнанки. Хранить на мягких вешалках.'
  },
  {
    id: 4,
    name: 'Пижама «Sofia» с шортами',
    category: 'pijama',
    material: 'satin',
    materialLabel: 'Сатин шёлковый',
    price: 4990,
    oldPrice: null,
    badge: 'hit',
    stock: 18,
    sizes: ['XS', 'S', 'M', 'L'],
    disabledSizes: [],
    colors: [
      { name: 'Пыльная роза', hex: '#C9A0A0' },
      { name: 'Чёрный', hex: '#1C1C1E' },
      { name: 'Лавандовый', hex: '#B8A9C9' }
    ],
    images: [
      placeholder('#C9A0A0', '«Sofia» — роза'),
      placeholder('#B89090', '«Sofia» — топ'),
      placeholder('#D4AFAF', '«Sofia» — шорты')
    ],
    description: 'Топ на тонких регулируемых бретелях с кружевом по декольте + шорты с кружевной отделкой. Лёгкая и женственная — идеальна для тёплых ночей.',
    care: 'Ручная стирка в прохладной воде. Не выжимать. Сушить в расправленном виде.'
  },
  {
    id: 5,
    name: 'Сорочка «Valentina»',
    category: 'nightgown',
    material: 'silk',
    materialLabel: 'Шёлк с кружевом',
    price: 5490,
    oldPrice: 6990,
    badge: null,
    stock: 3,
    sizes: ['XS', 'S', 'M', 'L'],
    disabledSizes: ['XS'],
    colors: [
      { name: 'Чёрный', hex: '#1C1C1E' },
      { name: 'Бордо', hex: '#6B2D3E' }
    ],
    images: [
      placeholder('#6B2D3E', '«Valentina» — бордо'),
      placeholder('#5B1D2E', '«Valentina» — спина'),
      placeholder('#7B3D4E', '«Valentina» — кружево')
    ],
    description: 'Длинная ночная сорочка из шёлка с кружевной вставкой на груди и разрезом по бедру. V-образный вырез на тонких бретелях. Длина ниже колена.',
    care: 'Только ручная стирка. Не отжимать. Гладить через ткань при минимальной температуре.'
  },
  {
    id: 6,
    name: 'Сорочка «Emilia» мини',
    category: 'nightgown',
    material: 'satin',
    materialLabel: 'Сатин + французское кружево',
    price: 3990,
    oldPrice: null,
    badge: 'new',
    stock: 15,
    sizes: ['XS', 'S', 'M', 'L', 'XL'],
    disabledSizes: [],
    colors: [
      { name: 'Пудровый', hex: '#E8C8C0' },
      { name: 'Чёрный', hex: '#2C2C2E' },
      { name: 'Молочный', hex: '#F5F0E8' }
    ],
    images: [
      placeholder('#E8C8C0', '«Emilia» — пудра'),
      placeholder('#D8B8B0', '«Emilia» — кружево'),
      placeholder('#F0D0C8', '«Emilia» — спина')
    ],
    description: 'Короткая сорочка из сатина с отделкой французским кружевом по лифу и подолу. Тонкие перекрёстные бретели на спине. Длина до середины бедра.',
    care: 'Ручная стирка при 30°. Не использовать отбеливатель. Сушить в расправленном виде.'
  },
  {
    id: 7,
    name: 'Комплект «Dolce Vita»',
    category: 'set',
    material: 'silk',
    materialLabel: 'Шёлк + кружево шантильи',
    price: 12990,
    oldPrice: 15990,
    badge: 'hit',
    stock: 4,
    sizes: ['S', 'M', 'L'],
    disabledSizes: [],
    colors: [
      { name: 'Чёрный', hex: '#1C1C1E' },
      { name: 'Пудровый', hex: '#E8C8C0' }
    ],
    images: [
      placeholder('#1C1C1E', '«Dolce Vita» — чёрный'),
      placeholder('#2C2C2E', '«Dolce Vita» — халат'),
      placeholder('#0C0C0E', '«Dolce Vita» — сорочка')
    ],
    description: 'Подарочный комплект: длинный шёлковый халат-кимоно + ночная сорочка с кружевом шантильи. В фирменной коробке Mia-Amore с атласной лентой.',
    care: 'Только ручная стирка. Халат и сорочку стирать отдельно. Гладить через ткань.'
  },
  {
    id: 8,
    name: 'Комплект «Notte»',
    category: 'set',
    material: 'satin',
    materialLabel: 'Сатин шёлковый, 5 предметов',
    price: 9990,
    oldPrice: null,
    badge: null,
    stock: 7,
    sizes: ['S', 'M', 'L', 'XL'],
    disabledSizes: [],
    colors: [
      { name: 'Бордо', hex: '#6B2D3E' },
      { name: 'Графит', hex: '#4A4A4E' }
    ],
    images: [
      placeholder('#6B2D3E', '«Notte» — бордо'),
      placeholder('#5B1D2E', '«Notte» — состав'),
      placeholder('#7B3D4E', '«Notte» — упаковка')
    ],
    description: 'Комплект из 5 предметов: халат + рубашка + брюки + топ на бретелях + шорты. Всё из шёлкового сатина в одном цвете. В подарочной упаковке.',
    care: 'Ручная стирка при 30°. Каждый предмет стирать отдельно. Не использовать отбеливатель.'
  },
  {
    id: 9,
    name: 'Халат «Aurora» с капюшоном',
    category: 'robe',
    material: 'silk',
    materialLabel: 'Шёлк стёганый',
    price: 11490,
    oldPrice: null,
    badge: null,
    stock: 5,
    sizes: ['S', 'M', 'L'],
    disabledSizes: ['S'],
    colors: [
      { name: 'Жемчужный', hex: '#F0EDE8' },
      { name: 'Графит', hex: '#4A4A4E' }
    ],
    images: [
      placeholder('#F0EDE8', '«Aurora» — жемчуг'),
      placeholder('#E0DDD8', '«Aurora» — капюшон'),
      placeholder('#D0CDC8', '«Aurora» — стёжка')
    ],
    description: 'Длинный стёганый халат из шёлка с капюшоном и накладными карманами. Лёгкий утеплитель внутри — тёплый, но не тяжёлый. Для прохладных вечеров.',
    care: 'Деликатная машинная стирка при 30°. Сушить в расправленном виде. Не гладить.'
  },
  {
    id: 10,
    name: 'Пижама «Lucia» брючная',
    category: 'pijama',
    material: 'satin',
    materialLabel: 'Сатин с кантом',
    price: 5490,
    oldPrice: 6490,
    badge: null,
    stock: 10,
    sizes: ['XS', 'S', 'M', 'L', 'XL'],
    disabledSizes: [],
    colors: [
      { name: 'Изумрудный', hex: '#2D6B5E' },
      { name: 'Тёмно-синий', hex: '#2C3E6B' },
      { name: 'Бордо', hex: '#6B2D3E' }
    ],
    images: [
      placeholder('#2D6B5E', '«Lucia» — изумруд'),
      placeholder('#1D5B4E', '«Lucia» — кант'),
      placeholder('#3D7B6E', '«Lucia» — брюки')
    ],
    description: 'Рубашка с длинным рукавом и контрастным кантом + брюки на мягкой резинке. Классический крой, перламутровые пуговицы. Выглядит дорого — стоит разумно.',
    care: 'Ручная стирка при 30°. Гладить с изнанки при низкой температуре.'
  }
];
