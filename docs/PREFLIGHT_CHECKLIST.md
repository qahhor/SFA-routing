# Pre-flight Checklist: SFA-Routing Beta Launch

## Чеклист готовности к Production

Используйте этот чеклист перед запуском в production.

---

## 1. Инфраструктура

### Сервер
- [ ] Ubuntu 22.04 LTS установлен
- [ ] Минимум 4 vCPU, 8GB RAM
- [ ] 100GB+ SSD доступно
- [ ] Статический IP адрес назначен
- [ ] Домен настроен (A-записи указывают на сервер)

### Сеть
- [ ] Firewall настроен (порты 22, 80, 443)
- [ ] SSH ключи настроены (пароли отключены)
- [ ] Fail2ban установлен (опционально)

### Docker
- [ ] Docker Engine 24.0+ установлен
- [ ] Docker Compose v2.20+ установлен
- [ ] Пользователь добавлен в группу docker

---

## 2. Конфигурация

### Environment (.env)
- [ ] `backend/.env` создан из `.env.production` шаблона
- [ ] `POSTGRES_PASSWORD` - уникальный сильный пароль (32+ символов)
- [ ] `SECRET_KEY` - сгенерирован заново (64+ символов)
- [ ] `ENVIRONMENT=production`
- [ ] `DEBUG=false`
- [ ] `LOG_LEVEL=INFO`
- [ ] `CORS_ORIGINS` - указаны реальные домены

### Nginx
- [ ] `docker/nginx/conf.d/default.conf` - server_name обновлён
- [ ] SSL сертификаты получены и размещены в `docker/nginx/ssl/`
- [ ] HTTPS блок раскомментирован (после настройки SSL)

### Docker Compose
- [ ] `docker-compose.prod.yml` просмотрен
- [ ] Resource limits адекватны серверу
- [ ] Volumes настроены правильно

---

## 3. Данные

### OSRM (картографические данные)
- [ ] OSM данные скачаны для нужного региона
- [ ] OSRM файлы подготовлены (extract, partition, customize)
- [ ] OSRM контейнер запускается без ошибок

### База данных
- [ ] PostgreSQL запускается
- [ ] Миграции Alembic выполнены (`alembic upgrade head`)
- [ ] Начальные данные загружены (если есть)

---

## 4. Безопасность

### Credentials
- [ ] Все дефолтные пароли изменены
- [ ] `.env` НЕ добавлен в git
- [ ] Секреты не логируются

### Сеть
- [ ] База данных НЕ доступна извне (ports: [] в prod)
- [ ] Redis НЕ доступен извне
- [ ] Metrics endpoint защищён (allow internal networks only)

### SSL/TLS
- [ ] HTTPS работает
- [ ] Сертификат валиден (не self-signed для production)
- [ ] Автообновление сертификатов настроено

---

## 5. Мониторинг

### Health Checks
- [ ] `/api/v1/health` отвечает 200
- [ ] `/api/v1/health/detailed` показывает все компоненты healthy

### Логирование
- [ ] Логи пишутся в JSON формате
- [ ] Ротация логов настроена (max-size, max-file)
- [ ] Логи доступны для просмотра

### Алерты (рекомендуется)
- [ ] Внешний мониторинг настроен (UptimeRobot, etc.)
- [ ] Уведомления настроены (email/telegram)

---

## 6. Резервное копирование

### Бэкапы
- [ ] Скрипт бэкапа работает (`./scripts/backup.sh`)
- [ ] Cron job для ежедневных бэкапов настроен
- [ ] Тестовое восстановление из бэкапа выполнено

### Rollback
- [ ] Скрипт rollback протестирован
- [ ] Документирована процедура отката

---

## 7. Тестирование

### Функциональность
- [ ] API эндпоинты отвечают корректно
- [ ] WebSocket подключение работает
- [ ] Оптимизация маршрутов работает
- [ ] Celery задачи выполняются

### Нагрузка (рекомендуется)
- [ ] Базовый нагрузочный тест проведён
- [ ] Система выдерживает ожидаемую нагрузку

---

## 8. Документация

### Техническая
- [ ] DEPLOYMENT_GUIDE_RU.md актуален
- [ ] MONITORING_RU.md актуален
- [ ] TROUBLESHOOTING_RU.md актуален

### Операционная
- [ ] Контакты ответственных задокументированы
- [ ] Процедура эскалации определена

---

## Команды для финальной проверки

```bash
# 1. Проверка статуса сервисов
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

# 2. Проверка здоровья API
curl -s http://localhost/api/v1/health/detailed | jq .

# 3. Проверка использования ресурсов
docker stats --no-stream

# 4. Проверка логов на ошибки
docker compose logs --tail=100 api | grep -i error

# 5. Проверка бэкапов
ls -la backups/

# 6. Тестовый запрос оптимизации
curl -X POST http://localhost/api/v1/delivery/optimize \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"order_ids": [], "vehicle_ids": [], "date": "2025-01-30"}'
```

---

## Go/No-Go Decision

| Категория | Статус |
|-----------|--------|
| Инфраструктура | ⬜ Ready / ⬜ Not Ready |
| Конфигурация | ⬜ Ready / ⬜ Not Ready |
| Данные | ⬜ Ready / ⬜ Not Ready |
| Безопасность | ⬜ Ready / ⬜ Not Ready |
| Мониторинг | ⬜ Ready / ⬜ Not Ready |
| Бэкапы | ⬜ Ready / ⬜ Not Ready |
| Тестирование | ⬜ Ready / ⬜ Not Ready |

**Решение:** ⬜ GO / ⬜ NO-GO

**Дата:** ________________

**Ответственный:** ________________

---

*Чеклист версия 1.0.0*
