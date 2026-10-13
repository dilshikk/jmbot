"""Вакансии для панели: список, создание, правка, включение/выключение."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aiohttp import web
from sqlalchemy import select

from bot.db.base import session_pool
from bot.db.models.vacancy import Vacancy

MAX_NAME_LEN = 60


def _dto(v: Vacancy) -> dict[str, Any]:
    return {
        "id": v.id,
        "name_ru": v.name_ru,
        "name_uz": v.name_uz,
        "emoji": v.emoji,
        "is_active": bool(v.is_active),
        "sort_order": v.sort_order,
    }


def _clean(body: dict[str, Any], key: str) -> str | None:
    value = body.get(key)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if 0 < len(value) <= MAX_NAME_LEN else None


async def list_vacancies(request: web.Request) -> web.Response:
    async with session_pool() as session:
        rows = (
            await session.scalars(select(Vacancy).order_by(Vacancy.sort_order, Vacancy.id))
        ).all()
    return web.json_response({"items": [_dto(v) for v in rows]})


async def create_vacancy(request: web.Request) -> web.Response:
    body = await request.json()
    name_ru, name_uz = _clean(body, "name_ru"), _clean(body, "name_uz")
    if not name_ru or not name_uz:
        return web.json_response({"error": "bad_name"}, status=400)
    emoji = str(body.get("emoji", "")).strip()[:8]

    async with session_pool() as session:
        last = (
            await session.scalars(select(Vacancy.sort_order).order_by(Vacancy.sort_order.desc()))
        ).first()
        vacancy = Vacancy(
            name_ru=name_ru,
            name_uz=name_uz,
            emoji=emoji,
            is_active=1,
            sort_order=(last or 0) + 1,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        session.add(vacancy)
        await session.commit()
        return web.json_response(_dto(vacancy))


async def update_vacancy(request: web.Request) -> web.Response:
    try:
        vacancy_id = int(request.match_info["vacancy_id"])
    except ValueError:
        return web.json_response({"error": "bad_id"}, status=400)
    body = await request.json()

    async with session_pool() as session:
        vacancy = await session.get(Vacancy, vacancy_id)
        if vacancy is None:
            return web.json_response({"error": "not_found"}, status=404)
        if "name_ru" in body:
            name = _clean(body, "name_ru")
            if not name:
                return web.json_response({"error": "bad_name"}, status=400)
            vacancy.name_ru = name
        if "name_uz" in body:
            name = _clean(body, "name_uz")
            if not name:
                return web.json_response({"error": "bad_name"}, status=400)
            vacancy.name_uz = name
        if "emoji" in body:
            vacancy.emoji = str(body["emoji"]).strip()[:8]
        if "is_active" in body:
            vacancy.is_active = 1 if body["is_active"] else 0
        await session.commit()
        return web.json_response(_dto(vacancy))
