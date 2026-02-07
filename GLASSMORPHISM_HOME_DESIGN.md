# Glassmorphism дизайн главной страницы (2026-02-07)

**Дата:** 2026-02-07  
**Концепция:** Современный минимализм с эффектом стекломорфизма (Glassmorphism)  
**Стиль:** "Дорого" выглядящий интерфейс с глубиной и воздухом

---

## Реализованные элементы

### 1. Mesh Gradient Background (Живой градиентный фон)

**Особенности:**
- **Анимированный фон:** 4 ellipse градиента с плавной анимацией (15s infinite)
- **Цвета (темная тема):**
  - Индиго: `rgba(79, 70, 229, 0.5)`
  - Фиолетовый: `rgba(139, 92, 246, 0.4)`
  - Синий: `rgba(59, 130, 246, 0.6)`
  - Голубой: `rgba(96, 165, 250, 0.3)`
  - Базовый градиент: `#1e1b4b → #1e3a8a → #0f172a`
- **Цвета (светлая тема):**
  - Приглушенные версии тех же цветов
  - Базовый: `#f8fafc → #e0e7ff → #dbeafe`
- **Позиция:** `fixed` (не прокручивается)
- **Анимация:** Плавное движение градиентов (keyframes mesh-gradient)

**Код:**
```css
.mesh-gradient-bg {
  position: fixed;
  background: 
    radial-gradient(ellipse at 18% 15%, rgba(79, 70, 229, 0.5) 0%, transparent 55%),
    radial-gradient(ellipse at 85% 40%, rgba(139, 92, 246, 0.4) 0%, transparent 55%),
    radial-gradient(ellipse at 45% 85%, rgba(59, 130, 246, 0.6) 0%, transparent 60%),
    radial-gradient(ellipse at 65% 20%, rgba(96, 165, 250, 0.3) 0%, transparent 50%),
    linear-gradient(125deg, #1e1b4b 0%, #1e3a8a 50%, #0f172a 100%);
  animation: mesh-gradient 15s ease infinite;
}
```

### 2. Header (Шапка)

**Структура:**
- **Главный заголовок:** "Easy Meet"
  - Размер: 48px
  - Вес: 900 (Black)
  - Эффект: Gradient text fill (белый → полупрозрачный белый)
  - Тень: `text-shadow: 0 4px 16px rgba(0, 0, 0, 0.4)`
- **Подзаголовок:** Описание приложения
  - Размер: 15px
  - Цвет: `rgba(255, 255, 255, 0.75)` (75% прозрачность)
  - Max-width: 320px (центрированный)

**Код:**
```css
.home-title {
  font-size: 48px;
  font-weight: 900;
  letter-spacing: -1px;
  background: linear-gradient(135deg, #fff 0%, rgba(255, 255, 255, 0.8) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
```

### 3. Glass Cards (Стеклянные карточки)

**Эффект стекла:**
- **Фон:** `rgba(255, 255, 255, 0.08)` (8% прозрачность)
- **Blur:** `backdrop-filter: blur(30px) saturate(180%)`
- **Граница:** `1px solid rgba(255, 255, 255, 0.18)` (тонкая светлая)
- **Border-radius:** 28px (сильное скругление)
- **Тени:**
  - Внешняя: `0 10px 40px rgba(0, 0, 0, 0.2)`
  - Внутренняя (верх): `inset 0 1px 0 rgba(255, 255, 255, 0.1)`
  - Внутренняя (низ): `inset 0 -1px 0 rgba(255, 255, 255, 0.05)`

**Hover эффект:**
- **Transform:** `translateY(-4px) scale(1.01)` (поднимается и слегка увеличивается)
- **Фон:** `rgba(255, 255, 255, 0.14)` (становится ярче)
- **Тень:** Увеличивается `0 16px 50px rgba(0, 0, 0, 0.25)`
- **Иконка:** `scale(1.1) rotate(5deg)` (увеличение + поворот)
- **Линия сверху:** Появляется gradient линия `::before`

**Active эффект:**
- **Transform:** `scale(0.97)` (легко сжимается)
- **Тень:** Уменьшается

**Структура карточки:**
```html
<Link to="/book" className="glass-card">
  <div className="glass-card-content">
    <div className="glass-card-icon">🗓️</div>
    <div className="glass-card-text">
      <h2 className="glass-card-title">Назначить встречу</h2>
      <p className="glass-card-subtitle">Выбрать слот</p>
    </div>
  </div>
</Link>
```

**Иконки:**
- Карточка 1: 🗓️ (календарь с плюсом)
- Карточка 2: 📋 (список/ежедневник)
- Размер: 52px
- Тень: `drop-shadow(0 4px 12px rgba(0, 0, 0, 0.3))`

### 4. Admin Footer (Админский футер)

**Особенности:**
- **Позиция:** `fixed bottom` (прилипает к низу)
- **Opacity:** 0.4 (очень незаметный)
- **Иконка:** ⚙️ (шестеренка)
- **Текст:** "Пульт управления"
- **Размер:** 13px (мелкий)
- **Цвет:** `rgba(255, 255, 255, 0.4)`

**Код:**
```css
.admin-footer-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.4);
  opacity: 0.4;
}
```

---

## Анимации

### 1. Mesh Gradient Animation
```css
@keyframes mesh-gradient {
  0%, 100% {
    background-position: 0% 0%, 100% 50%, 50% 100%, 80% 20%, 0% 0%;
  }
  50% {
    background-position: 100% 20%, 0% 80%, 30% 0%, 60% 90%, 0% 0%;
  }
}
```

### 2. Card Hover Animation
- **Transition:** `all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1)` (bounce-like)
- **Icon transform:** `transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1)`

---

## Адаптивность

### Темная тема (Dark Mode)
- Mesh gradient: Яркие, насыщенные цвета (индиго, фиолетовый, синий)
- Glass cards: `rgba(255, 255, 255, 0.08)` (прозрачный белый)
- Текст: Белый с тенями

### Светлая тема (Light Mode)
- Mesh gradient: Приглушенные, пастельные цвета
- Glass cards: `rgba(255, 255, 255, 0.75)` (более непрозрачный)
- Текст: Темный (`#1e293b`)

---

## Haptic Feedback

**Добавлено для:**
- Клик на "Назначить встречу" → `haptic.light()`
- Клик на "Мои записи" → `haptic.light()`

---

## Файлы изменены

### Новые стили (index.css):
- `.mesh-gradient-bg` — анимированный градиентный фон
- `.glass-card` — стеклянные карточки
- `.glass-card-content` — layout карточки
- `.glass-card-icon` — иконка (с анимацией)
- `.glass-card-title` — заголовок карточки
- `.glass-card-subtitle` — подзаголовок
- `.home-header` — шапка страницы
- `.home-title` — главный заголовок "Easy Meet"
- `.home-subtitle` — подзаголовок
- `.admin-footer` — футер админа
- `.admin-footer-link` — ссылка в футере

### Компонент (Home.tsx):
- Добавлен mesh gradient фон (`<div className="mesh-gradient-bg" />`)
- Переделана структура: header + glass cards + admin footer
- Добавлен haptic feedback

---

## Визуальные референсы

### Glassmorphism эффект:
- **Backdrop blur:** 30px (сильное размытие)
- **Saturate:** 180% (усиление цветов фона)
- **Прозрачность:** 8-14% (очень прозрачные карточки)
- **Граница:** Тонкая светлая для эффекта края стекла

### Mesh Gradient:
- **4 ellipse градиента** разных размеров и позиций
- **Анимация 15 секунд** с плавным движением
- **Базовый линейный градиент** для глубины

### Типографика:
- **Главный заголовок:** 48px, 900 weight, gradient fill
- **Заголовки карточек:** 22px, 700 weight, белый/темный
- **Подзаголовки:** 15px, 400 weight, 75% прозрачность

---

## Сравнение "До" и "После"

### До:
- Простые белые карточки (`.card`)
- Сплошной фон (`var(--tg-bg)`)
- Обычные тени
- Стандартный заголовок "Запись встречи"

### После:
- Glassmorphism карточки с blur
- Живой анимированный mesh gradient фон
- Глубокие многослойные тени
- Эффектный заголовок "Easy Meet" с gradient
- Анимация иконок при hover
- Bounce-like transition

---

## Производительность

**Оптимизации:**
- `backdrop-filter` кешируется браузером
- `transform` использует GPU (hardware acceleration)
- `will-change` не используется (не нужно для таких простых анимаций)
- `fixed` фон — рендерится один раз

**Размер бандла:**
- CSS: 9.33 KB (gzip: 2.56 KB)
- JS: 252.91 KB (gzip: 80.11 KB)

---

## Готово! ✨

Главная страница теперь имеет:
✅ Живой mesh gradient фон с анимацией  
✅ Glassmorphism карточки с эффектом стекла  
✅ Плавные bounce-like анимации  
✅ Haptic feedback  
✅ Адаптация под светлую/темную тему  
✅ "Дорогой" premium вид  

**Следующий шаг:** Протестировать в Telegram (@google_calendar_booking1_bot)
