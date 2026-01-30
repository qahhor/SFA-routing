#!/usr/bin/env python3
"""
Пример: Оптимизация маршрутов доставки (VRP)

Сценарий:
1. Создаём транспорт с ограничениями грузоподъёмности
2. Создаём заказы с временными окнами
3. Запускаем оптимизацию маршрутов
4. Анализируем результаты
5. Демонстрируем переоптимизацию при отмене заказа

Запуск:
    python example_delivery_optimization.py
"""

from datetime import date, datetime, timedelta
from sfa_client import SFAClient, SFAClientError


def main():
    client = SFAClient("http://localhost:8000")

    try:
        # 1. Аутентификация
        print("🔐 Логин...")
        client.login("dispatcher", "password")
        print("   ✅ Успешно\n")

        # 2. Создание транспорта
        print("🚛 Создание транспорта...")

        vehicles = []

        # Газель (лёгкий груз)
        v1 = client.vehicles.create(
            name="Газель NN-001",
            license_plate="01A001AA",
            capacity_kg=1500,
            capacity_volume_m3=12,
            start_latitude=41.311081,
            start_longitude=69.279737,
            work_start="08:00",
            work_end="20:00",
            driver_name="Бахром Юсупов",
            driver_phone="+998901111111",
        )
        vehicles.append(v1)
        print(f"   🚐 {v1['name']}: {v1['capacity_kg']} кг")

        # Фургон (средний груз)
        v2 = client.vehicles.create(
            name="Isuzu NN-002",
            license_plate="01A002AA",
            capacity_kg=3000,
            capacity_volume_m3=20,
            start_latitude=41.311081,
            start_longitude=69.279737,
            work_start="07:00",
            work_end="19:00",
            driver_name="Санжар Рахимов",
            driver_phone="+998902222222",
        )
        vehicles.append(v2)
        print(f"   🚚 {v2['name']}: {v2['capacity_kg']} кг\n")

        # 3. Создание клиентов для доставки
        print("🏪 Создание точек доставки...")

        delivery_points = [
            ("Супермаркет Макро", 41.328, 69.255, "09:00", "12:00"),
            ("Корзинка Юнусабад", 41.365, 69.285, "09:00", "14:00"),
            ("Гипермаркет Хамкор", 41.295, 69.220, "10:00", "15:00"),
            ("Магазин Барака", 41.340, 69.270, "08:00", "11:00"),
            ("Озиқ-овқат Центр", 41.275, 69.285, "11:00", "16:00"),
            ("Продукты 24", 41.305, 69.295, "14:00", "18:00"),
            ("Korzinka Чиланзар", 41.285, 69.205, "09:00", "13:00"),
            ("Минимаркет Сергели", 41.245, 69.215, "10:00", "17:00"),
        ]

        clients = []
        for i, (name, lat, lon, tw_start, tw_end) in enumerate(delivery_points):
            c = client.clients.create(
                name=name,
                external_id=f"DLV-{i + 1:03d}",
                address=f"Ташкент, {name}",
                latitude=lat,
                longitude=lon,
                category="B",
                time_window_start=tw_start,
                time_window_end=tw_end,
            )
            clients.append(c)
            print(f"   📍 {name} ({tw_start}-{tw_end})")

        print(f"\n   ✅ Создано {len(clients)} точек доставки\n")

        # 4. Создание заказов
        print("📦 Создание заказов...")

        tomorrow = date.today() + timedelta(days=1)
        orders = []

        order_data = [
            # (client_index, weight_kg, volume_m3, priority)
            (0, 250, 2.0, 8),  # Супермаркет Макро - срочный
            (1, 180, 1.5, 5),  # Корзинка Юнусабад
            (2, 400, 3.0, 6),  # Гипермаркет Хамкор
            (3, 120, 1.0, 9),  # Магазин Барака - очень срочный
            (4, 300, 2.5, 4),  # Озиқ-овқат Центр
            (5, 150, 1.2, 5),  # Продукты 24
            (6, 500, 4.0, 7),  # Korzinka Чиланзар
            (7, 200, 1.8, 3),  # Минимаркет Сергели
        ]

        for i, (client_idx, weight, volume, priority) in enumerate(order_data):
            c = clients[client_idx]
            tw_start = datetime.combine(tomorrow, datetime.strptime(c["time_window_start"], "%H:%M").time())
            tw_end = datetime.combine(tomorrow, datetime.strptime(c["time_window_end"], "%H:%M").time())

            order = client.delivery.create_order(
                client_id=c["id"],
                external_id=f"ORD-{tomorrow.strftime('%Y%m%d')}-{i + 1:03d}",
                weight_kg=weight,
                volume_m3=volume,
                time_window_start=tw_start,
                time_window_end=tw_end,
                priority=priority,
            )
            orders.append(order)
            print(f"   📦 Заказ {order['external_id']}: {weight} кг → {c['name']} (приоритет: {priority})")

        total_weight = sum(o["weight_kg"] for o in orders)
        print(f"\n   ✅ Создано {len(orders)} заказов")
        print(f"      Общий вес: {total_weight} кг\n")

        # 5. Оптимизация маршрутов
        print("🧮 Запуск оптимизации маршрутов...")
        print("   Солвер: auto (система выберет оптимальный)")
        print("   Ограничения: грузоподъёмность, временные окна\n")

        result = client.delivery.optimize(
            order_ids=[o["id"] for o in orders],
            vehicle_ids=[v["id"] for v in vehicles],
            route_date=tomorrow,
            solver="auto",  # auto, vroom, ortools, genetic
            minimize_vehicles=True,
            respect_time_windows=True,
        )

        # 6. Анализ результатов
        print("📊 Результаты оптимизации:")
        print("=" * 70)

        routes = result.get("routes", [])
        unassigned = result.get("unassigned", [])
        summary = result.get("summary", {})

        print(f"\n📈 Общая статистика:")
        print(f"   Маршрутов создано: {len(routes)}")
        print(f"   Заказов распределено: {summary.get('assigned_orders', len(orders) - len(unassigned))}")
        print(f"   Нераспределённых: {len(unassigned)}")
        print(f"   Общая дистанция: {summary.get('total_distance_km', 0):.1f} км")
        print(f"   Общее время: {summary.get('total_duration_minutes', 0):.0f} мин")

        for i, route in enumerate(routes, 1):
            vehicle_name = route.get("vehicle", {}).get("name", "Unknown")
            stops = route.get("stops", [])
            distance = route.get("total_distance_km", 0)
            duration = route.get("total_duration_minutes", 0)
            load = route.get("total_weight_kg", 0)

            print(f"\n🚛 Маршрут {i}: {vehicle_name}")
            print(f"   Загрузка: {load} кг | Дистанция: {distance:.1f} км | Время: {duration:.0f} мин")
            print(f"   Остановки ({len(stops)}):")

            for j, stop in enumerate(stops, 1):
                client_name = stop.get("client", {}).get("name", "Unknown")
                arrival = stop.get("planned_arrival", "??:??")
                weight = stop.get("order", {}).get("weight_kg", 0)
                print(f"      {j}. {arrival} - {client_name} ({weight} кг)")

        if unassigned:
            print(f"\n⚠️ Нераспределённые заказы ({len(unassigned)}):")
            for order_id in unassigned:
                print(f"   - {order_id}")

        # 7. Переоптимизация при отмене заказа
        print("\n" + "=" * 70)
        print("\n🔄 Демонстрация переоптимизации:")
        print("   Сценарий: отмена одного заказа\n")

        if routes:
            route_id = routes[0]["id"]
            cancelled_order = orders[0]

            print(f"   ❌ Отменяем заказ: {cancelled_order['external_id']}")

            new_result = client.delivery.reoptimize(
                route_id=route_id,
                reason="order_cancelled",
                excluded_order_ids=[cancelled_order["id"]],
            )

            print(f"   ✅ Маршрут переоптимизирован")
            new_distance = new_result.get("total_distance_km", 0)
            print(f"      Новая дистанция: {new_distance:.1f} км")

        print("\n🎉 Пример завершён!")

    except SFAClientError as e:
        print(f"❌ Ошибка API: {e.message}")
        if e.details:
            print(f"   Детали: {e.details}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
