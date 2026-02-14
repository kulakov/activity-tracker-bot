"""
Стратегический движок: объединяет данные, промпты и психологические механики.
Основные функции:
- Gate-механизм (2 стратегических → 1 fun)
- Гештальт-менеджер (эффект Зейгарник)
- Novelty engine (разнообразие внутри фокуса)
- Утреннее брифинг
- Рекомендации при переключении задач
"""

import random
from typing import Optional, List, Tuple

from strategic_data import StrategicData
from strategic_prompts import (
    STARTER_PROMPTS, TASK_TYPES, LARP_NARRATIVES,
    format_starter_prompt, get_random_narrative
)


class StrategicEngine:
    """Центральный координатор стратегического фокуса."""

    def __init__(self):
        self.data = StrategicData()

    def reload(self):
        self.data.load()

    # ── 1. Снижение порога входа ─────────────────────────────

    def get_starter_prompts(self, goal_id: Optional[str] = None,
                            task_type: Optional[str] = None,
                            count: int = 3) -> List[Tuple[dict, dict]]:
        """
        Возвращает [(prompt_data, goal), ...] — готовые стартовые промпты.
        Микширует по типам для novelty.
        """
        candidates = []
        goals = self.data.get_goals()

        for goal in goals:
            if goal_id and goal["id"] != goal_id:
                continue
            prompts = STARTER_PROMPTS.get(goal["id"], [])
            for p in prompts:
                if task_type and p["type"] != task_type:
                    continue
                candidates.append((p, goal))

        # Перемешиваем и берём count, стараясь миксовать типы
        random.shuffle(candidates)
        if len(candidates) <= count:
            return candidates

        # Пытаемся набрать разные типы
        selected = []
        used_types = set()
        for c in candidates:
            if c[0]["type"] not in used_types:
                selected.append(c)
                used_types.add(c[0]["type"])
                if len(selected) >= count:
                    break
        # Добиваем если не хватило
        for c in candidates:
            if c not in selected:
                selected.append(c)
                if len(selected) >= count:
                    break
        return selected[:count]

    def format_starter_menu(self, goal_id: Optional[str] = None) -> str:
        """Форматирует меню стартовых промптов для показа пользователю."""
        prompts = self.get_starter_prompts(goal_id=goal_id)
        if not prompts:
            return "Нет доступных задач. Добавь квесты через /quest"

        lines = ["🚀 **Готовые стартовые задачи** (выбери номер):\n"]
        for i, (prompt_data, goal) in enumerate(prompts, 1):
            task_type = TASK_TYPES.get(prompt_data["type"], {"icon": "📋"})
            lines.append(
                f"{i}. {goal['icon']} {task_type['icon']} **{prompt_data['title']}**\n"
                f"   {prompt_data['duration']}  |  +{prompt_data['xp']} XP\n"
            )
        lines.append("\nОтправь номер задачи или /goals для выбора цели")
        return "\n".join(lines)

    # ── 2. Feedback loop и quick wins ────────────────────────

    def complete_strategic_task(self, goal_id: str, quest_id: str,
                                task_id: str) -> str:
        """Завершает задачу и возвращает feedback-сообщение с LARP-нарративом."""
        old_level = self.data.get_player()["level"]

        completed_quest = self.data.complete_task(goal_id, quest_id, task_id)
        self.data.update_streak()

        messages = []

        # Задача выполнена
        messages.append(get_random_narrative("task_complete", xp=5))

        # Квест завершён?
        if completed_quest:
            messages.append(get_random_narrative(
                "quest_complete",
                quest=completed_quest["title"],
                xp=completed_quest["xp_reward"]
            ))

        # Левел-ап?
        new_level = self.data.get_player()["level"]
        if new_level > old_level:
            player = self.data.get_player()
            messages.append(get_random_narrative(
                "level_up",
                level=new_level,
                title=player["title"]
            ))

        # Серия?
        streak = self.data.get_player()["streak"]
        if streak > 1 and streak % 3 == 0:  # Каждые 3 дня показываем
            messages.append(get_random_narrative("streak", streak=streak))

        # Gate-статус
        messages.append(self.data.get_gate_status())

        # Что дальше?
        next_suggestion = self.data.suggest_next_strategic_task()
        if next_suggestion:
            messages.append(f"\n📋 Следующая задача:\n{next_suggestion}")

        # Variable reward: случайный ракурс
        if random.random() < 0.3:  # 30% шанс
            angle = self.data.get_random_angle(goal_id)
            messages.append(f"\n💡 Мысль: {angle}")

        return "\n\n".join(messages)

    # ── 3. Task switching management ─────────────────────────

    def get_switch_suggestion(self) -> str:
        """Когда пользователь хочет переключиться — предлагаем стратегическое."""
        suggestion = self.data.suggest_next_strategic_task()
        if suggestion:
            # Находим goal для иконки
            result = self.data.get_next_task()
            if result:
                goal, quest, task = result
                return get_random_narrative(
                    "switch_nudge",
                    suggestion=suggestion,
                    goal_icon=goal["icon"],
                    goal_title=goal["title"]
                )
        return "Все стратегические задачи выполнены! Можно переключиться на fun."

    def check_fun_gate(self) -> Tuple[bool, str]:
        """Проверяет gate: можно ли заниматься fun-проектом."""
        allowed = self.data.is_fun_allowed()
        if allowed:
            return True, get_random_narrative("gate_unlocked")
        else:
            fg = self.data._data["fun_gate"]
            remaining = fg["strategic_required"] - fg["strategic_done_today"]
            return False, get_random_narrative("gate_locked", remaining=remaining)

    def record_fun_activity(self) -> str:
        """Записывает fun-активность и обновляет gate."""
        self.data.record_fun_task()
        return (
            "🎮 Fun-задача записана!\n"
            f"{self.data.get_gate_status()}"
        )

    # ── 4. Гештальт-менеджмент ───────────────────────────────

    def create_gestalt(self, goal_id: str, description: str,
                       progress: int = 0) -> str:
        """Создаёт открытый гештальт — незавершённую задачу, которая 'тянет' обратно."""
        self.data.add_gestalt(goal_id, description, progress)
        goal = self.data.get_goal(goal_id)
        goal_title = goal["title"] if goal else "?"
        return (
            f"📌 Новый открытый гештальт ({goal_title}):\n"
            f"«{description}» — {progress}%\n"
            f"Это будет напоминать о себе, пока не завершишь."
        )

    def get_gestalt_reminder(self) -> Optional[str]:
        """Возвращает напоминание о незавершённом гештальте (для утреннего брифинга)."""
        return self.data.get_gestalt_nudge()

    # ── 5. Novelty внутри стратегического фокуса ─────────────

    def get_novelty_suggestion(self, goal_id: str) -> str:
        """Возвращает новый ракурс + задачу другого типа для разнообразия."""
        angle = self.data.get_random_angle(goal_id)
        prompts = self.get_starter_prompts(goal_id=goal_id, count=1)
        if prompts:
            p, goal = prompts[0]
            task_type = TASK_TYPES.get(p["type"], {"icon": "📋", "label": "Задача"})
            return (
                f"💡 {angle}\n\n"
                f"Попробуй: {task_type['icon']} {p['title']}\n"
                f"{p['prompt']}"
            )
        return f"💡 {angle}"

    # ── 6. Morning briefing ──────────────────────────────────

    def get_morning_briefing(self) -> str:
        """Утренний брифинг: статус, гештальты, рекомендация, gate."""
        player = self.data.get_player()
        status = self.data.get_player_status_text()
        gestalt = self.get_gestalt_reminder() or "Нет открытых гештальтов."
        suggestion = self.data.suggest_next_strategic_task() or "Добавь квесты через /quest"
        gate = self.data.get_gate_status()

        return get_random_narrative(
            "morning_briefing",
            title=player["title"],
            status=status,
            gestalt=gestalt,
            suggestion=suggestion,
            gate=gate
        )

    # ── 7. Decomposition helper ──────────────────────────────

    def decompose_goal_to_quests(self, goal_id: str) -> str:
        """Показывает предложения по декомпозиции цели на квесты."""
        goal = self.data.get_goal(goal_id)
        if not goal:
            return "Цель не найдена"

        templates = {
            "jetstyle_growth": [
                ("Аудит текущей воронки продаж", "main", [
                    "Выгрузить данные из CRM за последний квартал",
                    "Найти 3 самых узких места в воронке",
                    "Для каждого узкого места — гипотеза и эксперимент",
                    "Запустить первый эксперимент",
                    "Замерить результат через неделю"
                ]),
                ("Новый AI-сервис для клиентов", "main", [
                    "Собрать 5 болей клиентов из последних проектов",
                    "Выбрать одну боль и описать решение",
                    "Сделать MVP за 1 день",
                    "Показать 3 клиентам и собрать фидбек",
                    "Доработать и запустить пилот"
                ]),
                ("Прокачка тимлидов", "side", [
                    "1-on-1 с каждым тимлидом: что мешает расти?",
                    "Собрать общий список блокеров",
                    "Выбрать 3 главных и составить план",
                    "Запустить первую инициативу"
                ]),
            ],
            "ai_products": [
                ("Подготовка IT-Regatta Barcelona", "main", [
                    "Определить формат выступления/воркшопа",
                    "Написать тезисы и outline",
                    "Подготовить 3 демо-кейса",
                    "Прогнать презентацию с коллегой",
                    "Финализировать материалы"
                ]),
                ("AI-воркшоп для CEO", "main", [
                    "Определить целевую аудиторию и боли",
                    "Разработать программу 2-часового воркшопа",
                    "Подготовить hands-on упражнения",
                    "Тестовый прогон на 3 человеках",
                    "Собрать фидбек и доработать"
                ]),
            ],
            "consulting": [
                ("Контент-план «Хороший Вопрос»", "main", [
                    "Собрать 20 тем из клиентских кейсов",
                    "Приоритизировать по резонансу",
                    "Написать 5 постов-черновиков",
                    "Опубликовать первые 3 и замерить отклик",
                    "Скорректировать стратегию контента"
                ]),
                ("Первый B2B-клиент на консалтинг", "main", [
                    "Описать оффер на 1 страницу",
                    "Определить 10 целевых компаний",
                    "Отправить 5 персональных предложений",
                    "Провести 2 discovery-созвона",
                    "Закрыть первую сделку"
                ]),
            ],
            "creative": [
                ("Прогресс Eternal Games", "side", [
                    "Написать outline следующей главы",
                    "Написать 1000 слов черновика",
                    "Отредактировать предыдущую главу",
                    "Показать бета-ридеру и собрать фидбек"
                ]),
                ("Дизайн LARP-механики", "side", [
                    "Описать core loop игры",
                    "Придумать 3 типа квестов для игроков",
                    "Протестировать одну механику на бумаге",
                    "Написать правила для плейтеста"
                ]),
            ]
        }

        suggestions = templates.get(goal_id, [])
        if not suggestions:
            return f"Для цели «{goal['title']}» пока нет шаблонов квестов. Опиши квест сам через /quest"

        lines = [f"{goal['icon']} **{goal['title']}** — варианты квестов:\n"]
        for i, (title, qtype, tasks) in enumerate(suggestions, 1):
            lines.append(f"{i}. **{title}** ({qtype})")
            for j, t in enumerate(tasks, 1):
                lines.append(f"   {j}. {t}")
            lines.append("")

        lines.append("Отправь номер квеста, чтобы добавить его в бэклог")
        return "\n".join(lines)

    def add_predefined_quest(self, goal_id: str, quest_index: int) -> Optional[str]:
        """Добавляет предопределённый квест из шаблонов."""
        templates = {
            "jetstyle_growth": [
                ("Аудит текущей воронки продаж", "main", [
                    "Выгрузить данные из CRM за последний квартал",
                    "Найти 3 самых узких места в воронке",
                    "Для каждого узкого места — гипотеза и эксперимент",
                    "Запустить первый эксперимент",
                    "Замерить результат через неделю"
                ]),
                ("Новый AI-сервис для клиентов", "main", [
                    "Собрать 5 болей клиентов из последних проектов",
                    "Выбрать одну боль и описать решение",
                    "Сделать MVP за 1 день",
                    "Показать 3 клиентам и собрать фидбек",
                    "Доработать и запустить пилот"
                ]),
                ("Прокачка тимлидов", "side", [
                    "1-on-1 с каждым тимлидом: что мешает расти?",
                    "Собрать общий список блокеров",
                    "Выбрать 3 главных и составить план",
                    "Запустить первую инициативу"
                ]),
            ],
            "ai_products": [
                ("Подготовка IT-Regatta Barcelona", "main", [
                    "Определить формат выступления/воркшопа",
                    "Написать тезисы и outline",
                    "Подготовить 3 демо-кейса",
                    "Прогнать презентацию с коллегой",
                    "Финализировать материалы"
                ]),
                ("AI-воркшоп для CEO", "main", [
                    "Определить целевую аудиторию и боли",
                    "Разработать программу 2-часового воркшопа",
                    "Подготовить hands-on упражнения",
                    "Тестовый прогон на 3 человеках",
                    "Собрать фидбек и доработать"
                ]),
            ],
            "consulting": [
                ("Контент-план «Хороший Вопрос»", "main", [
                    "Собрать 20 тем из клиентских кейсов",
                    "Приоритизировать по резонансу",
                    "Написать 5 постов-черновиков",
                    "Опубликовать первые 3 и замерить отклик",
                    "Скорректировать стратегию контента"
                ]),
                ("Первый B2B-клиент на консалтинг", "main", [
                    "Описать оффер на 1 страницу",
                    "Определить 10 целевых компаний",
                    "Отправить 5 персональных предложений",
                    "Провести 2 discovery-созвона",
                    "Закрыть первую сделку"
                ]),
            ],
            "creative": [
                ("Прогресс Eternal Games", "side", [
                    "Написать outline следующей главы",
                    "Написать 1000 слов черновика",
                    "Отредактировать предыдущую главу",
                    "Показать бета-ридеру и собрать фидбек"
                ]),
                ("Дизайн LARP-механики", "side", [
                    "Описать core loop игры",
                    "Придумать 3 типа квестов для игроков",
                    "Протестировать одну механику на бумаге",
                    "Написать правила для плейтеста"
                ]),
            ]
        }

        suggestions = templates.get(goal_id, [])
        if quest_index < 0 or quest_index >= len(suggestions):
            return None

        title, qtype, tasks = suggestions[quest_index]
        quest = self.data.add_quest(goal_id, title, qtype, tasks)
        if quest:
            # Создаём гештальт для первой задачи
            self.data.add_gestalt(goal_id, f"{title}: {tasks[0]}", 0)
            return (
                f"{get_random_narrative('quest_start')}\n\n"
                f"Квест «{title}» добавлен!\n"
                f"Задач: {len(tasks)}  |  XP за квест: +{quest['xp_reward']}\n\n"
                f"Первый шаг: {tasks[0]}\n"
                f"Используй /next чтобы начать."
            )
        return None

    # ── Progress summary ─────────────────────────────────────

    def get_weekly_summary(self) -> str:
        """Недельная сводка прогресса."""
        completions = self.data.get_recent_completions(7)
        player = self.data.get_player()

        if not completions:
            return "На этой неделе пока нет завершённых задач. Начни с /focus!"

        total_xp = sum(c.get("xp", 0) for c in completions)
        goals_touched = set(c["goal"] for c in completions)

        lines = [
            f"📊 **Неделя {player['title']}а**\n",
            f"✅ Задач выполнено: {len(completions)}",
            f"✨ XP заработано: {total_xp}",
            f"🎯 Целей затронуто: {len(goals_touched)}",
            f"🔥 Текущая серия: {player['streak']} дн.",
            ""
        ]

        # Группируем по целям
        by_goal = {}
        for c in completions:
            by_goal.setdefault(c["goal"], []).append(c)

        for goal_name, tasks in by_goal.items():
            lines.append(f"**{goal_name}**: {len(tasks)} задач")
            for t in tasks[:3]:  # Показываем до 3
                lines.append(f"  • {t['task']}")
            if len(tasks) > 3:
                lines.append(f"  ... и ещё {len(tasks)-3}")
            lines.append("")

        return "\n".join(lines)
