# 書 KiriCallig — Кириллическая каллиграфия

Генератор кириллического шрифта в стиле японской каллиграфии (書道, Shodo), построенный на базе [VecGlypher](https://github.com/xk-huang/VecGlypher) — мультимодальной языковой модели для генерации векторных глифов.

## Идея

Объединить эстетику японской каллиграфии — динамику кисти, переходы от толстых штрихов к тонким, органичную текучесть — с кириллическими буквами. VecGlypher генерирует глифы как SVG-пути напрямую через LLM, что позволяет задавать стиль текстовым описанием.

## Стили

| Стиль | Описание | Аналог |
|-------|----------|--------|
| `default` | Сбалансированный каллиграфический стиль с динамичными штрихами | — |
| `kaisho` | Формальный стиль, чёткие штрихи, структурированные формы | 楷書 |
| `gyosho` | Полукурсив, плавные переходы, читаемый | 行書 |
| `sosho` | Травяное письмо, экспрессивный, абстрактный | 草書 |
| `modern` | Минималистичный современный стиль с элементами кисти | — |

## Требования

- Python 3.11+
- Conda
- GPU с CUDA (рекомендуется, минимум 16GB VRAM для Qwen3-4B)
- ~10GB дискового пространства для модели

## Быстрый старт

```bash
# Полный пайплайн (установка + генерация + сборка шрифта)
bash generate.sh --style default

# Или пошагово:

# 1. Установка окружения и модели
bash scripts/setup_env.sh

# 2. Активация окружения
conda activate cyrillic_calligraphy

# 3. Подготовка данных для инференса
python scripts/prepare_inference_data.py --style default --chars all

# 4. Запуск инференса
bash scripts/run_inference.sh --style default

# 5. Предпросмотр глифов
python scripts/preview_glyphs.py --style default

# 6. Сборка шрифта
python scripts/assemble_font.py --style default
```

## Пошаговое описание пайплайна

### 1. `setup_env.sh` — Установка

- Клонирует VecGlypher в `third_party/`
- Создаёт conda-окружение `cyrillic_calligraphy`
- Устанавливает зависимости (LLaMA Factory, vLLM, fonttools)
- Скачивает предобученную модель с HuggingFace

### 2. `prepare_inference_data.py` — Подготовка данных

Создаёт JSONL-файлы с промптами для VecGlypher. Каждый промпт содержит:
- **Системный промпт**: инструкция для генерации SVG-путей
- **Описание стиля**: текстовые теги каллиграфического стиля
- **Целевой символ**: кириллический символ для генерации

Формат (Alpaca):
```json
{
  "system": "You are a specialized vector glyph designer...",
  "instruction": "Font design requirements: display, handwritten, calligraphic, brush-stroke...\nText content: А",
  "input": "",
  "output": ""
}
```

### 3. `run_inference.sh` — Инференс

- Запускает vLLM-сервер с моделью VecGlypher
- Отправляет батч-запросы через OpenAI-совместимый API
- Сохраняет результаты в JSONL

### 4. `extract_svgs.py` — Извлечение SVG

Парсит ответы модели и создаёт отдельные SVG-файлы для каждого глифа.

### 5. `preview_glyphs.py` — Предпросмотр

Генерирует HTML-страницу с визуальной сеткой всех глифов для проверки качества.

### 6. `assemble_font.py` — Сборка шрифта

Собирает SVG-глифы в TrueType-шрифт (.ttf) с помощью fonttools:
- Конвертирует SVG-пути в контуры шрифта
- Инвертирует ось Y (SVG → font coordinate system)
- Устанавливает метрики, кодовые страницы (Cyrillic), метаданные

## Структура проекта

```
cyrillic-calligraphy-font/
├── generate.sh                    # Главный скрипт (полный пайплайн)
├── README.md
├── configs/
│   └── style_config.py            # Стили, параметры, метаданные шрифта
├── data/
│   ├── cyrillic_chars.py          # Набор кириллических символов
│   └── inference_input/           # Сгенерированные JSONL для инференса
├── scripts/
│   ├── setup_env.sh               # Установка окружения
│   ├── prepare_inference_data.py  # Подготовка промптов
│   ├── run_inference.sh           # Запуск инференса
│   ├── extract_svgs.py            # Извлечение SVG из результатов
│   ├── preview_glyphs.py          # HTML-предпросмотр
│   └── assemble_font.py           # Сборка .ttf
├── output/
│   ├── svgs/                      # Отдельные SVG-глифы
│   ├── font/                      # Готовый шрифт
│   └── preview.html               # HTML-предпросмотр
├── models/                        # Скачанные модели (gitignored)
└── third_party/                   # VecGlypher (gitignored)
```

## Набор символов

- 33 прописные буквы (А-Я, Ё)
- 33 строчные буквы (а-я, ё)
- 10 цифр (0-9)
- Знаки препинания: . , ; : ! ? - – — ( ) « » " ' …

Всего: ~95 глифов

## Ограничения и заметки

- VecGlypher обучался преимущественно на латинских символах из Google Fonts. Качество генерации кириллических символов может быть ниже — модель может интерпретировать незнакомые формы неожиданно.
- Для лучших результатов стоит:
  - Генерировать несколько вариантов каждого глифа и выбирать лучший
  - Использовать `temperature=0.7` для баланса разнообразия и качества
  - Ручная пост-обработка в редакторе шрифтов (FontForge, Glyphs)
- Для Ъ, Ы, Щ и других сложных кириллических форм качество может быть хуже — они далеки от латинского алфавита.

## Благодарности

- [VecGlypher](https://github.com/xk-huang/VecGlypher) — Huang et al., CVPR 2026
- [fonttools](https://github.com/fonttools/fonttools)
- [svgpathtools](https://github.com/mathandy/svgpathtools)
