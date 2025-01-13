import json
import os

class Categories:
    def __init__(self):
        self.filename = 'categories.json'
        self.load_categories()
    
    def load_categories(self):
        if os.path.exists(self.filename):
            with open(self.filename, 'r', encoding='utf-8') as f:
                self._data = json.load(f)
        else:
            self._data = {
                'КОНТЕКСТЫ': [],
                'РОЛИ': {
                    'Управленческие': {},
                    'Экспертные': {},
                    'Образовательные': {},
                    'Социальные': {}
                },
                'ДОБЫЧА': {
                    'Энергия': {},
                    'Целевые': {},
                    'Проблемы': {}
                },
                'СКИЛЫ': {
                    'Базовые': {},
                    'Энергозатратные': {},
                    'Энергия': {},
                    'Целевые': {}
                },
                'ВЕРДИКТЫ': {},
                'ЦЕЛИ': {}
            }
            self.save_categories()
    
    def save_categories(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
    
    def add_category(self, category_type, value, subcategory=None):
        """Добавление новой категории"""
        if category_type not in self._data:
            return False
            
        if subcategory:
            if subcategory not in self._data[category_type]:
                return False
            if value not in self._data[category_type][subcategory]:
                self._data[category_type][subcategory][value] = {}
        else:
            if value not in self._data[category_type]:
                self._data[category_type].append(value)
                
        self.save_categories()
        return True

# Системный промпт для ChatGPT
SYSTEM_PROMPT = """Ты помощник для анализа транскриптов и определения активностей. 
Твоя задача - анализировать текст на основе предоставленного справочника категорий и создавать структурированный конспект.

Формат вывода должен быть строго в следующем виде:
1. Хронология
2. Добыча и анализ (с тегами)
3. Фолоуп
4. Мета-анализ

Каждая активность должна быть размечена тегами в формате:
[контекст] [роль] действие | подробности
[цвет] навык | где применялся

Используй только теги из справочника.
"""

# Основной промпт для анализа
ANALYSIS_PROMPT = """
{справочник_категорий}

Проанализируй следующий текст, используя указанный выше справочник категорий:

{текст}

Создай структурированный конспект, следуя формату из системного промпта.
"""