# Pre-flight Checklist: SFA-Routing Beta v1.1 Launch

## Чеклист готовности к Production

Используйте этот чеклист перед запуском Beta версии в production.
Последнее обновление: Январь 2025

---

## 1. Инфраструктура

### 1.1 Сервер
- [ ] Ubuntu 22.04 LTS установлен
- [ ] Минимум 4 vCPU, 8GB RAM (рекомендуется 8 vCPU, 16GB)
- [ ] 100GB+ SSD доступно (NVMe предпочтительно)
- [ ] Статический IP адрес назначен
- [ ] Домен настроен (A-записи указывают на сервер)
- [ ] Часовой пояс настроен: `timedatectl set-timezone Asia/Tashkent`

### 1.2 Сеть
- [ ] Firewall настроен (UFW)
  ```bash
  sudo ufw allow 22/tcp   # SSH
  sudo ufw allow 80/tcp   # HTTP
  sudo ufw allow 443/tcp  # HTTPS
  sudo ufw enable
  ```
- [ ] SSH ключи настроены (пароли отключены)
- [ ] Fail2ban установлен (рекомендуется)

### 1.3 Docker
- [ ] Docker Engine 24.0+ установлен
  ```bash
  docker --version  # должно быть >= 24.0
  ```
- [ ] Docker Compose v2.20+ установлен
  ```bash
  docker compose version  # должно быть >= 2.20
  ```
- [ ] Пользователь добавлен в группу docker
  ```bash
  groups $USER | grep docker
  ```

---

## 2. Конфигурация

### 2.1 Environment (.env)
- [ ] `backend/.env` создан из `.env.production.example` шаблона
  ```bash
  cp backend/.env.production.example backend/.env
  ```
- [ ] `ENVIRONMENT=production`
- [ ] `DEBUG=false`
- [ ] `LOG_LEVEL=INFO`
- [ ] `POSTGRES_PASSWORD` - уникальный сильный пароль (32+ символов)
  ```bash
  openssl rand -base64 32
  ```
- [ ] `SECRET_KEY` - сгенерирован заново (64+ символов)
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(64))"
  ```
- [ ] `CORS_ORIGINS` - указаны реальные домены фронтенда
- [ ] `DATABASE_URL` - обновлён с новым паролем

### 2.2 Nginx
- [ ] `docker/nginx/conf.d/default.conf` - server_name обновлён
- [ ] SSL сертификаты получены и размещены в `docker/nginx/ssl/`
- [ ] HTTPS блок раскомментирован (после настройки SSL)

### 2.3 Docker Compose
- [ ] `docker-compose.prod.yml` просмотрен
- [ ] Resource limits адекватны серверу
- [ ] Volumes настроены правильно

---

## 3. Данные

### 3.1 OSRM (картографические данные)
- [ ] OSM данные скачаны для нужного региона
  ```bash
  cd docker/osrm
  wget https://download.geofabrik.de/asia/uzbekistan-latest.osm.pbf
  ```
- [ ] OSRM файлы подготовлены (extract, partition, customize)
  ```bash
  make osrm-setup  # или вручную, см. DEPLOYMENT_GUIDE
  ```
- [ ] OSRM контейнер запускается без ошибок

### 3.2 База данных
- [ ] PostgreSQL запускается
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d db
  docker compose exec db pg_isready
  ```
- [ ] Миграции Alembic выполнены
  ```bash
  docker compose exec api alembic upgrade head
  ```
- [ ] Начальные данные загружены (если есть)

---

## 4. Безопасность

### 4.1 Credentials
- [ ] ВСЕ дефолтные пароли изменены
- [ ] `.env` НЕ добавлен в git (проверьте `.gitignore`)
- [ ] Секреты не логируются (LOG_LEVEL=INFO, не DEBUG)
- [ ] `GEO_ENCRYPTION_KEY` сгенерирован (если используется шифрование координат)

### 4.2 Сеть
- [ ] База данных НЕ доступна извне (ports: [] в prod)
- [ ] Redis НЕ доступен извне (ports: [] в prod)
- [ ] Metrics endpoint защищён (allow internal networks only)
- [ ] WebSocket эндпоинты требуют аутентификации

### 4.3 SSL/TLS
- [ ] HTTPS работает
- [ ] Сертификат валиден (не self-signed для production)
  ```bash
  curl -I https://api.yourdomain.com/api/v1/health
  ```
- [ ] Автообновление сертификатов настроено (cron job)
- [ ] TLS 1.2+ (проверить в nginx.conf)

---

## 5. Мониторинг

### 5.1 Health Checks
- [ ] `/api/v1/health` отвечает 200
  ```bash
  curl http://localhost/api/v1/health
  ```
- [ ] `/api/v1/health/detailed` показывает все компоненты healthy
  ```bash
  curl http://localhost/api/v1/health/detailed | jq .
  ```

### 5.2 Логирование
- [ ] Логи пишутся в JSON формате
- [ ] Ротация логов настроена (max-size, max-file в docker-compose.prod.yml)
- [ ] Логи доступны для просмотра
  ```bash
  docker compose logs --tail=100 api
  ```

### 5.3 Алерты (рекомендуется)
- [ ] Внешний мониторинг настроен (UptimeRobot, etc.)
  - URL: `https://api.yourdomain.com/api/v1/health`
  - Интервал: 1-5 минут
- [ ] Уведомления настроены (email/telegram)
- [ ] Sentry DSN настроен для отслеживания ошибок (опционально)

---

## 6. Резервное копирование

### 6.1 Бэкапы
- [ ] Скрипт бэкапа работает
  ```bash
  ./scripts/backup.sh --compress
  ls -la backups/
  ```
- [ ] Cron job для ежедневных бэкапов настроен
  ```bash
  crontab -l | grep backup
  # Должно быть: 0 2 * * * /opt/sfa-routing/scripts/backup.sh --daily --compress
  ```
- [ ] Тестовое восстановление из бэкапа выполнено
  ```bash
  ./scripts/rollback.sh --list-backups
  ```

### 6.2 Rollback
- [ ] Скрипт rollback протестирован
- [ ] Документирована процедура отката

---

## 7. Тестирование

### 7.1 Функциональность
- [ ] API эндпоинты отвечают корректно
  ```bash
  curl http://localhost/api/v1/agents
  curl http://localhost/api/v1/clients
  ```
- [ ] WebSocket подключение работает
- [ ] Оптимизация маршрутов работает
  ```bash
  curl -X POST http://localhost/api/v1/delivery/optimize \
    -H "Content-Type: application/json" \
    -d '{"order_ids": [], "vehicle_ids": [], "date": "2025-01-30"}'
  ```
- [ ] Celery задачи выполняются
  ```bash
  docker compose exec celery celery -A app.core.celery_app inspect active
  ```

### 7.2 Нагрузка (рекомендуется)
- [ ] Базовый нагрузочный тест проведён
- [ ] Система выдерживает ожидаемую нагрузку (50+ RPS)

---

## 8. Документация

### 8.1 Техническая
- [ ] DEPLOYMENT_GUIDE_RU.md актуален
- [ ] MONITORING_RU.md актуален
- [ ] TROUBLESHOOTING_RU.md актуален
- [ ] API_REFERENCE.md актуален

### 8.2 Операционная
- [ ] Контакты ответственных задокументированы
- [ ] Процедура эскалации определена
- [ ] Runbook для частых проблем создан

---

## Команды для финальной проверки

```bash
# 1. Статус всех сервисов
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

# 2. Health check
curl -s http://localhost/api/v1/health/detailed | jq .

# 3. Использование ресурсов
docker stats --no-stream

# 4. Проверка логов на ошибки
docker compose logs --tail=100 api | grep -i error

# 5. Проверка бэкапов
ls -la backups/

# 6. Тест OSRM
curl "http://localhost:5001/route/v1/driving/69.24,41.31;69.28,41.32"

# 7. Тест оптимизации (пустой запрос)
curl -X POST http://localhost/api/v1/delivery/optimize \
  -H "Content-Type: application/json" \
  -d '{"order_ids": [], "vehicle_ids": [], "date": "2025-01-30"}'

# 8. Проверка SSL (если настроен)
curl -I https://api.yourdomain.com/api/v1/health
```

---

## Go/No-Go Decision

| Категория | Статус | Комментарий |
|-----------|--------|-------------|
| Инфраструктура | ⬜ Ready / ⬜ Not Ready | |
| Конфигурация | ⬜ Ready / ⬜ Not Ready | |
| Данные | ⬜ Ready / ⬜ Not Ready | |
| Безопасность | ⬜ Ready / ⬜ Not Ready | |
| Мониторинг | ⬜ Ready / ⬜ Not Ready | |
| Бэкапы | ⬜ Ready / ⬜ Not Ready | |
| Тестирование | ⬜ Ready / ⬜ Not Ready | |
| Документация | ⬜ Ready / ⬜ Not Ready | |

**Финальное решение:** ⬜ **GO** / ⬜ **NO-GO**

**Дата проверки:** ________________

**Ответственный:** ________________

**Подпись:** ________________

---

## Контакты для эскалации

| Роль | Имя | Контакт |
|------|-----|---------|
| DevOps | | |
| Backend Lead | | |
| DBA | | |
| Product Owner | | |

---

*Чеклист версия 1.1.0 - Beta Production Ready*
