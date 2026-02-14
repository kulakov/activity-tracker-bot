"""
Модель данных для стратегического фокуса.
Хранит цели, квесты, задачи, прогресс и LARP-механики.
"""

import json
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


DATA_FILE = 'strategic_goals.json'


def _now_str() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def _today() -> str:
    return datetime.now().strftime('%Y-%m-%d')


class StrategicData:
    """Центральное хранилище стратегических данных."""

    def __init__(self):
        self.load()

    # ── Persistence ──────────────────────────────────────────

    def load(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                self._data = json.load(f)
        else:
            self._data = self._default_data()
            self.save()

    def save(self):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def _default_data(self) -> dict:
        return {
            "goals": [
                {
                    "id": "jetstyle_growth",
                    "title": "Рост JetStyle 2026",
                    "description": "Выручка, позиционирование, масштабирование команды",
                    "icon": "🏢",
                    "xp": 0,
                    "quests": []
                },
                {
                    "id": "ai_products",
                    "title": "AI-продукты и воркшопы",
                    "description": "IT-Regatta Barcelona, AI-сервисы, обучение",
                    "icon": "🤖",
                    "xp": 0,
                    "quests": []
                },
                {
                    "id": "consulting",
                    "title": "Консалтинг «Хороший Вопрос»",
                    "description": "Telegram-канал, B2B-консалтинг, публичные выступления",
                    "icon": "💡",
                    "xp": 0,
                    "quests": []
                },
                {
                    "id": "creative",
                    "title": "Творческие проекты",
                    "description": "Eternal Games, Невидимый монах, детективные романы",
                    "icon": "🎭",
                    "xp": 0,
                    "quests": []
                }
            ],
            "player": {
                "level": 1,
                "total_xp": 0,
                "title": "Стратег-новичок",
                "streak": 0,
                "last_strategic_date": None,
                "daily_strategic_count": 0,
                "daily_fun_count": 0,
                "daily_date": None
            },
            "task_log": [],
            "open_gestalts": [],
            "fun_gate": {
                "strategic_required": 2,
                "strategic_done_today": 0,
                "fun_allowed": False
            }
        }

    # ── Goals ────────────────────────────────────────────────

    def get_goals(self) -> List[dict]:
        return self._data["goals"]

    def get_goal(self, goal_id: str) -> Optional[dict]:
        for g in self._data["goals"]:
            if g["id"] == goal_id:
                return g
        return None

    def add_goal(self, goal_id: str, title: str, description: str, icon: str = "🎯") -> dict:
        goal = {
            "id": goal_id,
            "title": title,
            "description": description,
            "icon": icon,
            "xp": 0,
            "quests": []
        }
        self._data["goals"].append(goal)
        self.save()
        return goal

    # ── Quests ───────────────────────────────────────────────

    def add_quest(self, goal_id: str, quest_title: str, quest_type: str = "main",
                  tasks: Optional[List[str]] = None) -> Optional[dict]:
        goal = self.get_goal(goal_id)
        if not goal:
            return None

        quest_id = f"q_{len(goal['quests'])+1}_{goal_id}"
        quest = {
            "id": quest_id,
            "title": quest_title,
            "type": quest_type,  # main, side, daily, research
            "status": "active",
            "created": _now_str(),
            "tasks": [],
            "xp_reward": self._quest_xp(quest_type),
            "progress": 0
        }

        if tasks:
            for i, t in enumerate(tasks):
                quest["tasks"].append({
                    "id": f"t_{i+1}",
                    "text": t,
                    "status": "pending",
                    "created": _now_str(),
                    "completed_at": None
                })

        goal["quests"].append(quest)
        self.save()
        return quest

    def _quest_xp(self, quest_type: str) -> int:
        return {"main": 50, "side": 30, "daily": 15, "research": 25}.get(quest_type, 20)

    def get_active_quests(self, goal_id: Optional[str] = None) -> List[Tuple[dict, dict]]:
        """Возвращает [(goal, quest), ...] для активных квестов."""
        result = []
        for goal in self._data["goals"]:
            if goal_id and goal["id"] != goal_id:
                continue
            for quest in goal["quests"]:
                if quest["status"] == "active":
                    result.append((goal, quest))
        return result

    def get_next_task(self, goal_id: Optional[str] = None) -> Optional[Tuple[dict, dict, dict]]:
        """Возвращает (goal, quest, task) — следующую незавершённую задачу."""
        for goal, quest in self.get_active_quests(goal_id):
            for task in quest["tasks"]:
                if task["status"] == "pending":
                    return (goal, quest, task)
        return None

    def complete_task(self, goal_id: str, quest_id: str, task_id: str) -> Optional[dict]:
        """Завершает задачу. Возвращает квест, если он завершён целиком."""
        goal = self.get_goal(goal_id)
        if not goal:
            return None

        for quest in goal["quests"]:
            if quest["id"] != quest_id:
                continue
            for task in quest["tasks"]:
                if task["id"] == task_id:
                    task["status"] = "done"
                    task["completed_at"] = _now_str()

            # Обновляем прогресс квеста
            done = sum(1 for t in quest["tasks"] if t["status"] == "done")
            total = len(quest["tasks"])
            quest["progress"] = int(done / total * 100) if total > 0 else 100

            if quest["progress"] == 100:
                quest["status"] = "completed"
                goal["xp"] += quest["xp_reward"]
                self._add_player_xp(quest["xp_reward"])

            self._log_task_completion(goal, quest, task)
            self._update_daily_counter("strategic")
            self.save()

            return quest if quest["progress"] == 100 else None

        return None

    # ── Player / LARP ────────────────────────────────────────

    def _add_player_xp(self, xp: int):
        p = self._data["player"]
        p["total_xp"] += xp
        # Уровни: 0-100 → 1, 100-250 → 2, 250-500 → 3, ...
        thresholds = [0, 100, 250, 500, 1000, 2000, 4000, 8000]
        titles = [
            "Стратег-новичок",
            "Тактик",
            "Архитектор роста",
            "Визионер",
            "Мастер-стратег",
            "CEO-легенда",
            "Гранд-стратег",
            "Властелин фокуса"
        ]
        for i, th in enumerate(thresholds):
            if p["total_xp"] >= th:
                p["level"] = i + 1
                p["title"] = titles[min(i, len(titles)-1)]

    def get_player(self) -> dict:
        return self._data["player"]

    def get_player_status_text(self) -> str:
        p = self._data["player"]
        goals = self._data["goals"]
        total_goal_xp = sum(g["xp"] for g in goals)

        lines = [
            f"⚔️ {p['title']} (уровень {p['level']})",
            f"✨ XP: {p['total_xp']}  |  Серия: {p['streak']} дн.",
            ""
        ]
        for g in goals:
            active = sum(1 for q in g["quests"] if q["status"] == "active")
            done = sum(1 for q in g["quests"] if q["status"] == "completed")
            lines.append(f"{g['icon']} {g['title']}: {g['xp']} XP  ({done} квестов завершено, {active} активных)")

        return "\n".join(lines)

    # ── Daily gate ───────────────────────────────────────────

    def _reset_daily_if_needed(self):
        today = _today()
        if self._data["fun_gate"].get("date") != today:
            self._data["fun_gate"]["strategic_done_today"] = 0
            self._data["fun_gate"]["fun_allowed"] = False
            self._data["fun_gate"]["date"] = today
            self._data["player"]["daily_strategic_count"] = 0
            self._data["player"]["daily_fun_count"] = 0
            self._data["player"]["daily_date"] = today

    def _update_daily_counter(self, kind: str):
        self._reset_daily_if_needed()
        if kind == "strategic":
            self._data["fun_gate"]["strategic_done_today"] += 1
            self._data["player"]["daily_strategic_count"] += 1
            req = self._data["fun_gate"]["strategic_required"]
            if self._data["fun_gate"]["strategic_done_today"] >= req:
                self._data["fun_gate"]["fun_allowed"] = True
        elif kind == "fun":
            self._data["player"]["daily_fun_count"] += 1
            # После fun-задачи сбрасываем gate: нужно ещё 2 стратегических
            self._data["fun_gate"]["fun_allowed"] = False
            self._data["fun_gate"]["strategic_done_today"] = 0
        self.save()

    def is_fun_allowed(self) -> bool:
        self._reset_daily_if_needed()
        return self._data["fun_gate"]["fun_allowed"]

    def get_gate_status(self) -> str:
        self._reset_daily_if_needed()
        fg = self._data["fun_gate"]
        done = fg["strategic_done_today"]
        req = fg["strategic_required"]
        if fg["fun_allowed"]:
            return f"🟢 Fun-режим разблокирован! (выполнено {done}/{req} стратегических задач)"
        remaining = req - done
        return f"🔒 До fun-режима: ещё {remaining} стратегических задач ({done}/{req})"

    def record_fun_task(self):
        self._update_daily_counter("fun")

    # ── Streak ───────────────────────────────────────────────

    def update_streak(self):
        p = self._data["player"]
        today = _today()
        last = p.get("last_strategic_date")
        if last == today:
            return  # уже обновили
        if last:
            last_date = datetime.strptime(last, '%Y-%m-%d').date()
            today_date = datetime.strptime(today, '%Y-%m-%d').date()
            if (today_date - last_date).days == 1:
                p["streak"] += 1
            elif (today_date - last_date).days > 1:
                p["streak"] = 1
        else:
            p["streak"] = 1
        p["last_strategic_date"] = today
        self.save()

    # ── Open gestalts ────────────────────────────────────────

    def add_gestalt(self, goal_id: str, description: str, progress_pct: int = 0):
        self._data["open_gestalts"].append({
            "goal_id": goal_id,
            "description": description,
            "progress": progress_pct,
            "created": _now_str()
        })
        self.save()

    def get_open_gestalts(self) -> List[dict]:
        return [g for g in self._data["open_gestalts"] if g["progress"] < 100]

    def complete_gestalt(self, index: int):
        if 0 <= index < len(self._data["open_gestalts"]):
            self._data["open_gestalts"][index]["progress"] = 100
            self.save()

    def get_gestalt_nudge(self) -> Optional[str]:
        """Возвращает напоминание о незавершённом гештальте (эффект Зейгарник)."""
        gestalts = self.get_open_gestalts()
        if not gestalts:
            return None
        # Выбираем тот, у которого максимальный прогресс (ближе к завершению — сильнее тянет)
        gestalts.sort(key=lambda g: g["progress"], reverse=True)
        top = gestalts[0]
        goal = self.get_goal(top["goal_id"])
        goal_title = goal["title"] if goal else "?"
        return (
            f"📌 Незавершённый гештальт ({goal_title}):\n"
            f"«{top['description']}» — прогресс {top['progress']}%\n"
            f"Хочешь закончить?"
        )

    # ── Task log ─────────────────────────────────────────────

    def _log_task_completion(self, goal: dict, quest: dict, task: dict):
        self._data["task_log"].append({
            "date": _now_str(),
            "goal": goal["title"],
            "quest": quest["title"],
            "task": task["text"],
            "xp": quest["xp_reward"] if quest.get("status") == "completed" else 5
        })
        # Храним последние 200 записей
        self._data["task_log"] = self._data["task_log"][-200:]

    def get_recent_completions(self, days: int = 7) -> List[dict]:
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        return [t for t in self._data["task_log"] if t["date"] >= cutoff]

    # ── Novelty & suggestions ────────────────────────────────

    def suggest_next_strategic_task(self) -> Optional[str]:
        """Предлагает следующую стратегическую задачу — с novelty."""
        result = self.get_next_task()
        if not result:
            return None
        goal, quest, task = result
        return (
            f"{goal['icon']} **{goal['title']}** → {quest['title']}\n"
            f"📋 Следующий шаг: {task['text']}\n"
            f"Прогресс квеста: {quest['progress']}%"
        )

    def get_random_angle(self, goal_id: str) -> str:
        """Подбрасывает неожиданный ракурс для стратегической задачи."""
        angles = {
            "jetstyle_growth": [
                "А что если посмотреть на это глазами клиента?",
                "Какой конкурент решил эту задачу элегантнее всего?",
                "Как бы выглядел MVP этого за 1 день?",
                "Что бы сказал твой CTO, если бы увидел это решение?",
                "Какой метрикой ты измеришь успех через месяц?",
            ],
            "ai_products": [
                "Какой AI-инструмент ты ещё не пробовал для этого?",
                "Как это можно превратить в воркшоп за 2 часа?",
                "Что если автоматизировать 80% и оставить 20% человеку?",
                "Как бы это выглядело через 3 года?",
                "Кто из участников IT-Regatta мог бы стать партнёром?",
            ],
            "consulting": [
                "Это тянет на пост в «Хороший Вопрос»?",
                "Какой вопрос клиент боится задать сам?",
                "Как сформулировать это как провокационный тезис?",
                "С кем из CEO стоит обсудить эту гипотезу?",
                "Как превратить это в кейс для выступления?",
            ],
            "creative": [
                "Какой персонаж увидел бы это иначе?",
                "Как добавить сюда элемент тайны?",
                "Что если это часть более крупного нарратива?",
                "Какая механика из LARP подходит здесь?",
                "Как бы детективный роман начинался с этой сцены?",
            ]
        }
        options = angles.get(goal_id, ["Посмотри на это с нового ракурса!"])
        return random.choice(options)
