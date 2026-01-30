#!/usr/bin/env python3
"""
Пример: Недельное планирование торгового представителя

Сценарий:
1. Создаём агента (торгового представителя)
2. Создаём клиентов разных категорий (A, B, C)
3. Генерируем недельный план
4. Просматриваем план на каждый день
5. Отмечаем выполнение визитов

Запуск:
    python example_weekly_planning.py
"""

from datetime import date, timedelta
from sfa_client import SFAClient, SFAClientError


def main():
    # Подключение к API
    client = SFAClient("http://localhost:8000")

    try:
        # 1. Аутентификация
        print("🔐 Логин...")
        client.login("dispatcher", "password")
        print("   ✅ Успешно\n")

        # 2. Создание агента
        print("👤 Создание агента...")
        agent = client.agents.create(
            name="Алишер Каримов",
            external_id="AGT-001",
            phone="+998901234567",
            start_latitude=41.311081,  # Ташкент, центр
            start_longitude=69.279737,
            work_start="09:00",
            work_end="18:00",
            max_visits_per_day=15,
        )
        print(f"   ✅ Агент создан: {agent['name']} (ID: {agent['id']})\n")

        # 3. Создание клиентов
        print("🏪 Создание клиентов...")

        # A-класс: 2-3 визита в неделю (ключевые клиенты)
        clients_a = []
        a_class_data = [
            ("Супермаркет Макро", 41.328, 69.255),
            ("Гипермаркет Корзинка", 41.295, 69.220),
            ("Korzinka.uz Чиланзар", 41.285, 69.205),
        ]
        for name, lat, lon in a_class_data:
            c = client.clients.create(
                name=name,
                external_id=f"CLT-A-{len(clients_a) + 1}",
                address=f"Ташкент, {name}",
                latitude=lat,
                longitude=lon,
                category="A",
                agent_id=agent["id"],
                visit_duration_minutes=25,
            )
            clients_a.append(c)
            print(f"   📍 A-класс: {c['name']}")

        # B-класс: 1 визит в неделю
        clients_b = []
        b_class_data = [
            ("Минимаркет у Анвара", 41.340, 69.270),
            ("Продукты 24/7", 41.305, 69.295),
            ("Магазин Барака", 41.290, 69.260),
            ("Дўкон Савдо", 41.320, 69.240),
            ("Озиқ-овқат Маркази", 41.275, 69.285),
        ]
        for name, lat, lon in b_class_data:
            c = client.clients.create(
                name=name,
                external_id=f"CLT-B-{len(clients_b) + 1}",
                address=f"Ташкент, {name}",
                latitude=lat,
                longitude=lon,
                category="B",
                agent_id=agent["id"],
                visit_duration_minutes=15,
            )
            clients_b.append(c)
            print(f"   📍 B-класс: {c['name']}")

        # C-класс: 1 визит в 2 недели
        clients_c = []
        c_class_data = [
            ("Киоск на Алайском", 41.315, 69.250),
            ("Ларёк у метро", 41.330, 69.280),
        ]
        for name, lat, lon in c_class_data:
            c = client.clients.create(
                name=name,
                external_id=f"CLT-C-{len(clients_c) + 1}",
                address=f"Ташкент, {name}",
                latitude=lat,
                longitude=lon,
                category="C",
                agent_id=agent["id"],
                visit_duration_minutes=10,
            )
            clients_c.append(c)
            print(f"   📍 C-класс: {c['name']}")

        total_clients = len(clients_a) + len(clients_b) + len(clients_c)
        print(f"\n   ✅ Создано {total_clients} клиентов")
        print(f"      A-класс: {len(clients_a)} (2-3 визита/неделю)")
        print(f"      B-класс: {len(clients_b)} (1 визит/неделю)")
        print(f"      C-класс: {len(clients_c)} (1 визит/2 недели)\n")

        # 4. Генерация недельного плана
        print("📅 Генерация недельного плана...")

        # Понедельник следующей недели
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        week_start = today + timedelta(days=days_until_monday)

        plan = client.planning.generate_weekly(
            agent_id=agent["id"],
            week_start_date=week_start,
            include_high_priority=True,
            respect_categories=True,
        )

        print(f"   ✅ План создан на неделю с {week_start}\n")

        # 5. Просмотр плана по дням
        print("📋 План на неделю:")
        print("=" * 60)

        days_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

        for i in range(5):  # Пн-Пт
            day_date = week_start + timedelta(days=i)
            daily = client.planning.get_daily_plan(agent["id"], day_date)

            print(f"\n{days_ru[i]} ({day_date}):")

            if daily.get("visits"):
                for j, visit in enumerate(daily["visits"], 1):
                    client_info = visit.get("client", {})
                    print(
                        f"   {j}. {visit.get('planned_time', '??:??')} - "
                        f"{client_info.get('name', 'Unknown')} "
                        f"[{client_info.get('category', '?')}]"
                    )
            else:
                print("   (нет запланированных визитов)")

        print("\n" + "=" * 60)

        # 6. Пример отметки выполнения визита
        print("\n✏️ Пример отметки выполнения визита:")

        # Получаем первый визит из плана
        monday_plan = client.planning.get_daily_plan(agent["id"], week_start)
        if monday_plan.get("visits"):
            first_visit = monday_plan["visits"][0]
            visit_id = first_visit["id"]

            # Отмечаем как выполненный
            updated = client.planning.update_visit(
                visit_id=visit_id,
                status="completed",
                actual_time="09:45",
                actual_duration_minutes=20,
                notes="Успешный визит. Заказ размещён на 500,000 сум.",
            )
            print(f"   ✅ Визит отмечен как выполненный")
            print(f"      Клиент: {first_visit.get('client', {}).get('name')}")
            print(f"      Статус: {updated.get('status')}")

        print("\n🎉 Пример завершён!")

    except SFAClientError as e:
        print(f"❌ Ошибка API: {e.message}")
        if e.details:
            print(f"   Детали: {e.details}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
