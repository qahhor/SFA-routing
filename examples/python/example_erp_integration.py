#!/usr/bin/env python3
"""
Пример: Интеграция с ERP через Webhooks и Bulk Import

Сценарий:
1. Регистрация webhook для получения событий
2. Массовый импорт заказов из ERP
3. Обработка webhook событий (пример сервера)

Запуск:
    python example_erp_integration.py
"""

import hmac
import hashlib
import json
from datetime import date, datetime, timedelta
from sfa_client import SFAClient, SFAClientError


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Проверка HMAC-SHA256 подписи webhook.

    Args:
        payload: Тело запроса в байтах
        signature: Подпись из заголовка X-Webhook-Signature
        secret: Секретный ключ

    Returns:
        True если подпись верна
    """
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def simulate_erp_orders() -> list[dict]:
    """Симуляция заказов из ERP системы (SmartUp, 1C и т.д.)."""
    tomorrow = date.today() + timedelta(days=1)

    return [
        {
            "external_id": f"ERP-{tomorrow.strftime('%Y%m%d')}-001",
            "client_external_id": "CLT-001",
            "weight_kg": 150,
            "volume_m3": 1.2,
            "time_window_start": f"{tomorrow}T09:00:00",
            "time_window_end": f"{tomorrow}T12:00:00",
            "priority": 8,
            "items": [
                {"sku": "PROD-001", "quantity": 50, "name": "Coca-Cola 1L"},
                {"sku": "PROD-002", "quantity": 30, "name": "Fanta 1L"},
            ]
        },
        {
            "external_id": f"ERP-{tomorrow.strftime('%Y%m%d')}-002",
            "client_external_id": "CLT-002",
            "weight_kg": 200,
            "volume_m3": 1.8,
            "time_window_start": f"{tomorrow}T10:00:00",
            "time_window_end": f"{tomorrow}T14:00:00",
            "priority": 5,
            "items": [
                {"sku": "PROD-003", "quantity": 100, "name": "Вода Nestle 0.5L"},
            ]
        },
        {
            "external_id": f"ERP-{tomorrow.strftime('%Y%m%d')}-003",
            "client_external_id": "CLT-003",
            "weight_kg": 300,
            "volume_m3": 2.5,
            "time_window_start": f"{tomorrow}T11:00:00",
            "time_window_end": f"{tomorrow}T16:00:00",
            "priority": 6,
            "items": [
                {"sku": "PROD-004", "quantity": 80, "name": "Sprite 1L"},
                {"sku": "PROD-005", "quantity": 40, "name": "Bonaqua 1.5L"},
            ]
        },
        {
            "external_id": f"ERP-{tomorrow.strftime('%Y%m%d')}-004",
            "client_external_id": "CLT-004",
            "weight_kg": 100,
            "volume_m3": 0.8,
            "time_window_start": f"{tomorrow}T08:00:00",
            "time_window_end": f"{tomorrow}T11:00:00",
            "priority": 9,  # Срочный
            "items": [
                {"sku": "PROD-001", "quantity": 20, "name": "Coca-Cola 1L"},
            ]
        },
        {
            "external_id": f"ERP-{tomorrow.strftime('%Y%m%d')}-005",
            "client_external_id": "CLT-005",
            "weight_kg": 250,
            "volume_m3": 2.0,
            "time_window_start": f"{tomorrow}T14:00:00",
            "time_window_end": f"{tomorrow}T18:00:00",
            "priority": 4,
            "items": [
                {"sku": "PROD-002", "quantity": 60, "name": "Fanta 1L"},
                {"sku": "PROD-003", "quantity": 50, "name": "Вода Nestle 0.5L"},
            ]
        },
    ]


def main():
    client = SFAClient("http://localhost:8000")

    try:
        # 1. Аутентификация
        print("🔐 Логин...")
        client.login("dispatcher", "password")
        print("   ✅ Успешно\n")

        # 2. Регистрация Webhook
        print("🔗 Регистрация webhook для интеграции с ERP...")
        print("   События: optimization.completed, route.updated, visit.completed\n")

        # В реальном сценарии это URL вашего ERP
        webhook_url = "https://your-erp.example.com/api/sfa-webhooks"
        webhook_secret = "your-webhook-secret-key-min-32-chars"

        # Пример структуры запроса (в реальности через API)
        webhook_config = {
            "url": webhook_url,
            "events": [
                "optimization.completed",  # Оптимизация завершена
                "route.updated",           # Маршрут обновлён
                "visit.completed",         # Визит завершён
                "delivery.completed",      # Доставка завершена
            ],
            "secret": webhook_secret,
            "retry_policy": {
                "max_attempts": 3,
                "backoff_seconds": [1, 2, 4]
            }
        }

        print(f"   URL: {webhook_url}")
        print(f"   События: {', '.join(webhook_config['events'])}")
        print("   ✅ Webhook зарегистрирован\n")

        # 3. Массовый импорт заказов из ERP
        print("📦 Массовый импорт заказов из ERP...")

        erp_orders = simulate_erp_orders()
        print(f"   Получено {len(erp_orders)} заказов из ERP\n")

        # Преобразование в формат API
        api_orders = []
        for order in erp_orders:
            api_orders.append({
                "external_id": order["external_id"],
                "client_external_id": order["client_external_id"],
                "weight_kg": order["weight_kg"],
                "volume_m3": order.get("volume_m3"),
                "time_window_start": order["time_window_start"],
                "time_window_end": order["time_window_end"],
                "priority": order.get("priority", 5),
            })

        # Идемпотентный импорт (безопасно повторять)
        import_date = date.today().strftime("%Y%m%d")
        idempotency_key = f"erp-import-{import_date}-batch-1"

        print(f"   Idempotency-Key: {idempotency_key}")

        result = client.bulk.import_orders(
            orders=api_orders,
            idempotency_key=idempotency_key
        )

        print(f"\n   📊 Результат импорта:")
        print(f"      Успешно: {result.get('successful', 0)}")
        print(f"      Ошибок: {result.get('failed', 0)}")
        print(f"      Дубликатов: {result.get('duplicates', 0)}")

        if result.get("errors"):
            print(f"      Детали ошибок:")
            for error in result["errors"][:3]:  # Первые 3
                print(f"         - {error}")

        # 4. Пример обработки webhook (код для вашего ERP сервера)
        print("\n" + "=" * 70)
        print("\n📥 Пример обработки webhook в ERP:")
        print("-" * 70)

        example_webhook_payload = {
            "event": "optimization.completed",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "optimization_id": "opt-123",
                "routes_count": 2,
                "orders_assigned": 5,
                "total_distance_km": 45.2,
                "total_duration_minutes": 180,
                "routes": [
                    {
                        "id": "route-1",
                        "vehicle_id": "veh-1",
                        "stops_count": 3,
                        "orders": ["ERP-001", "ERP-002", "ERP-004"]
                    },
                    {
                        "id": "route-2",
                        "vehicle_id": "veh-2",
                        "stops_count": 2,
                        "orders": ["ERP-003", "ERP-005"]
                    }
                ]
            }
        }

        print("""
# Пример Flask/FastAPI обработчика webhook:

from flask import Flask, request, abort
import hmac
import hashlib

app = Flask(__name__)
WEBHOOK_SECRET = "your-webhook-secret-key-min-32-chars"

@app.route('/api/sfa-webhooks', methods=['POST'])
def handle_sfa_webhook():
    # 1. Проверка подписи
    signature = request.headers.get('X-Webhook-Signature')
    if not signature:
        abort(401, 'Missing signature')

    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        request.data,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(f"sha256={expected}", signature):
        abort(401, 'Invalid signature')

    # 2. Обработка события
    payload = request.json
    event_type = payload['event']

    if event_type == 'optimization.completed':
        # Обновить статусы заказов в ERP
        for route in payload['data']['routes']:
            for order_id in route['orders']:
                update_erp_order_status(order_id, 'ROUTED')

    elif event_type == 'delivery.completed':
        # Закрыть заказ в ERP
        order_id = payload['data']['order_id']
        close_erp_order(order_id)

    return {'status': 'ok'}, 200
        """)

        print("-" * 70)
        print("\n   Пример payload события optimization.completed:")
        print(json.dumps(example_webhook_payload, indent=2, ensure_ascii=False))

        # 5. Синхронизация статусов
        print("\n" + "=" * 70)
        print("\n🔄 Пример синхронизации статусов ERP → SFA:")
        print("-" * 70)

        print("""
# Периодическая синхронизация (cron job каждые 5 минут):

def sync_erp_to_sfa():
    # 1. Получить изменённые заказы из ERP
    changed_orders = erp.get_orders_changed_since(last_sync_time)

    for order in changed_orders:
        if order.status == 'CANCELLED':
            # Отменить в SFA
            sfa.delivery.cancel_order(order.external_id)

        elif order.status == 'UPDATED':
            # Обновить детали
            sfa.delivery.update_order(
                external_id=order.external_id,
                weight_kg=order.weight,
                time_window_start=order.delivery_from,
                time_window_end=order.delivery_to,
            )

    # 2. Получить выполненные визиты из SFA
    completed = sfa.planning.get_completed_visits(since=last_sync_time)

    for visit in completed:
        # Обновить в ERP
        erp.update_client_visit(
            client_id=visit.client_external_id,
            visit_date=visit.actual_date,
            visit_time=visit.actual_time,
            notes=visit.notes,
            order_placed=visit.order_amount > 0,
        )
        """)

        print("\n🎉 Пример интеграции завершён!")
        print("\nДля production используйте:")
        print("  1. HTTPS endpoints для webhooks")
        print("  2. Очереди сообщений (RabbitMQ/Kafka) для надёжности")
        print("  3. Retry логику при временных сбоях")
        print("  4. Мониторинг webhook deliveries")

    except SFAClientError as e:
        print(f"❌ Ошибка API: {e.message}")
        if e.details:
            print(f"   Детали: {e.details}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
