# Руководство по развертыванию SFA-Routing

## Оглавление

1. [Требования к инфраструктуре](#1-требования-к-инфраструктуре)
2. [Предварительная подготовка](#2-предварительная-подготовка)
3. [Установка и настройка](#3-установка-и-настройка)
4. [Развертывание](#4-развертывание)
5. [Настройка SSL/TLS](#5-настройка-ssltls)
6. [Проверка работоспособности](#6-проверка-работоспособности)
7. [Пост-деплойные задачи](#7-пост-деплойные-задачи)

---

## 1. Требования к инфраструктуре

### 1.1 Минимальные требования (до 50 пользователей)

| Компонент | Требование |
|-----------|------------|
| **CPU** | 4 vCPU |
| **RAM** | 8 GB |
| **Диск** | 100 GB SSD |
| **ОС** | Ubuntu 22.04 LTS / Debian 12 |
| **Сеть** | Статический IP, открытые порты 80, 443 |

### 1.2 Рекомендуемые требования (50-500 пользователей)

| Компонент | Требование |
|-----------|------------|
| **CPU** | 8 vCPU |
| **RAM** | 16 GB |
| **Диск** | 200 GB SSD (NVMe предпочтительно) |
| **ОС** | Ubuntu 22.04 LTS |
| **Сеть** | Dedicated IP, Load Balancer |

### 1.3 Требования к программному обеспечению

- Docker Engine 24.0+
- Docker Compose v2.20+
- Git 2.34+
- curl, wget
- OpenSSL (для генерации сертификатов)

---

## 2. Предварительная подготовка

### 2.1 Установка Docker

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка зависимостей
sudo apt install -y ca-certificates curl gnupg lsb-release

# Добавление GPG ключа Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Добавление репозитория
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установка Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Добавление текущего пользователя в группу docker
sudo usermod -aG docker $USER
newgrp docker

# Проверка установки
docker --version
docker compose version
```

### 2.2 Настройка firewall

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
sudo ufw status
```

### 2.3 Создание системного пользователя

```bash
# Создание пользователя для приложения
sudo useradd -r -s /bin/bash -m -d /opt/sfa-routing sfa
sudo usermod -aG docker sfa

# Настройка прав
sudo mkdir -p /opt/sfa-routing
sudo chown -R sfa:sfa /opt/sfa-routing
```

---

## 3. Установка и настройка

### 3.1 Клонирование репозитория

```bash
# От имени пользователя sfa
sudo -u sfa -i
cd /opt/sfa-routing

git clone https://github.com/your-org/sfa-routing.git .
```

### 3.2 Настройка переменных окружения

```bash
# Копирование шаблона
cp backend/.env.example backend/.env

# Редактирование конфигурации
nano backend/.env
```

**Обязательные переменные для production:**

```bash
# =================================
# КРИТИЧЕСКИ ВАЖНЫЕ НАСТРОЙКИ
# =================================

# Окружение
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# База данных (ОБЯЗАТЕЛЬНО ИЗМЕНИТЕ ПАРОЛЬ!)
DATABASE_URL=postgresql+asyncpg://routeuser:YOUR_STRONG_PASSWORD_HERE@db:5432/routes
POSTGRES_USER=routeuser
POSTGRES_PASSWORD=YOUR_STRONG_PASSWORD_HERE
POSTGRES_DB=routes

# Секретный ключ (сгенерируйте новый!)
# Генерация: python3 -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=YOUR_64_CHAR_SECRET_KEY_HERE

# Redis
REDIS_URL=redis://redis:6379

# Внешние сервисы
OSRM_URL=http://osrm:5000
VROOM_URL=http://vroom:3000

# CORS (укажите ваш домен)
CORS_ORIGINS=["https://app.yourdomain.com"]

# =================================
# ОПЦИОНАЛЬНЫЕ НАСТРОЙКИ
# =================================

# Мониторинг (Sentry)
# SENTRY_DSN=https://your-sentry-dsn@sentry.io/project

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT_PER_MINUTE=60

# JWT токены
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### 3.3 Генерация безопасных ключей

```bash
# Генерация SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# Генерация пароля для базы данных
openssl rand -base64 32
```

### 3.4 Подготовка директорий

```bash
# Создание необходимых директорий
mkdir -p backups logs docker/nginx/ssl docker/osrm

# Настройка прав
chmod 700 backups
chmod 755 logs
```

---

## 4. Развертывание

### 4.1 Подготовка OSRM данных (опционально)

Для работы с реальными картографическими данными необходимо подготовить OSRM:

```bash
# Скачивание картографических данных для Узбекистана
cd docker/osrm
wget https://download.geofabrik.de/asia/uzbekistan-latest.osm.pbf

# Извлечение графа (занимает время, ~5-10 минут)
docker run -t -v $(pwd):/data osrm/osrm-backend osrm-extract -p /opt/car.lua /data/uzbekistan-latest.osm.pbf

# Создание разделов
docker run -t -v $(pwd):/data osrm/osrm-backend osrm-partition /data/uzbekistan-latest.osrm

# Кастомизация
docker run -t -v $(pwd):/data osrm/osrm-backend osrm-customize /data/uzbekistan-latest.osrm

cd ../..
```

### 4.2 Сборка и запуск

```bash
# Очистка от артефактов разработки
./scripts/cleanup.sh

# Полное развертывание (сборка + миграции + запуск)
./scripts/deploy.sh --full

# Или пошагово:
# 1. Сборка образов
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# 2. Запуск сервисов
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 3. Миграции базы данных
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api alembic upgrade head
```

### 4.3 Проверка запуска

```bash
# Статус контейнеров
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

# Просмотр логов
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api

# Проверка API
curl http://localhost/api/v1/health
```

---

## 5. Настройка SSL/TLS

### 5.1 Вариант A: Certbot (Let's Encrypt)

```bash
# Установка Certbot
sudo apt install -y certbot

# Остановка nginx для получения сертификата
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop nginx

# Получение сертификата
sudo certbot certonly --standalone -d api.yourdomain.com -d app.yourdomain.com

# Копирование сертификатов
sudo cp /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem docker/nginx/ssl/
sudo cp /etc/letsencrypt/live/api.yourdomain.com/privkey.pem docker/nginx/ssl/
sudo chown sfa:sfa docker/nginx/ssl/*.pem

# Активация HTTPS в nginx конфиге
# Раскомментируйте HTTPS блок в docker/nginx/conf.d/default.conf

# Запуск nginx
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d nginx
```

### 5.2 Вариант B: Собственные сертификаты

```bash
# Копирование сертификатов
cp /path/to/your/fullchain.pem docker/nginx/ssl/
cp /path/to/your/privkey.pem docker/nginx/ssl/

# Настройка прав
chmod 600 docker/nginx/ssl/*.pem
```

### 5.3 Автоматическое обновление сертификатов

```bash
# Создание скрипта обновления
cat > /opt/sfa-routing/scripts/renew-ssl.sh << 'EOF'
#!/bin/bash
certbot renew --quiet
cp /etc/letsencrypt/live/api.yourdomain.com/*.pem /opt/sfa-routing/docker/nginx/ssl/
docker compose -f /opt/sfa-routing/docker-compose.yml -f /opt/sfa-routing/docker-compose.prod.yml exec nginx nginx -s reload
EOF

chmod +x /opt/sfa-routing/scripts/renew-ssl.sh

# Добавление в crontab
echo "0 3 * * * /opt/sfa-routing/scripts/renew-ssl.sh" | sudo crontab -
```

---

## 6. Проверка работоспособности

### 6.1 Чеклист готовности

```bash
# 1. Все контейнеры запущены
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps --format "table {{.Name}}\t{{.Status}}"

# 2. API отвечает
curl -s http://localhost/api/v1/health | jq .

# 3. Детальная проверка здоровья
curl -s http://localhost/api/v1/health/detailed | jq .

# 4. База данных доступна
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec db pg_isready

# 5. Redis работает
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec redis redis-cli ping

# 6. Celery worker активен
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec celery celery -A app.core.celery_app inspect ping
```

### 6.2 Тестирование API

```bash
# Проверка документации API
curl -s http://localhost/api/v1/docs

# Тестовый запрос (требует аутентификации в production)
curl -X POST http://localhost/api/v1/planning/weekly \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test", "week_start_date": "2025-01-27"}'
```

### 6.3 Проверка WebSocket

```bash
# Установка websocat (если не установлен)
# cargo install websocat

# Тестирование WebSocket подключения
# websocat ws://localhost/ws/gps/test-agent
```

---

## 7. Пост-деплойные задачи

### 7.1 Настройка автоматических бэкапов

```bash
# Добавление ежедневного бэкапа в 2:00
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/sfa-routing/scripts/backup.sh --daily --compress") | crontab -

# Проверка crontab
crontab -l
```

### 7.2 Настройка мониторинга

```bash
# Проверка метрик Prometheus (если включено)
curl http://localhost/metrics

# Настройка внешнего мониторинга (например, UptimeRobot)
# URL для проверки: https://api.yourdomain.com/api/v1/health
```

### 7.3 Настройка логирования

```bash
# Просмотр логов в JSON формате
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 api | jq .

# Ротация логов уже настроена в docker-compose.prod.yml
# max-size: 50m, max-file: 5
```

### 7.4 Создание первого администратора

```bash
# Подключение к контейнеру API
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api bash

# Создание пользователя через CLI (если реализовано)
# python -m app.cli create-admin --email admin@example.com
```

---

## Полезные команды

### Управление сервисами

```bash
# Запуск
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Остановка
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# Перезапуск одного сервиса
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api

# Просмотр логов
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail=100 api celery

# Выполнение команды в контейнере
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api bash
```

### Обслуживание

```bash
# Обновление приложения
git pull
./scripts/deploy.sh --full

# Ручной бэкап
./scripts/backup.sh --compress

# Откат базы данных
./scripts/rollback.sh --db backups/daily_20250129_020000.sql.gz

# Очистка Docker (осторожно!)
docker system prune -a --volumes
```

### Отладка

```bash
# Проверка использования ресурсов
docker stats

# Проверка сетевых подключений
docker network inspect sfa-routing_route-network

# Проверка томов
docker volume ls
```

---

## Контакты и поддержка

При возникновении проблем:

1. Проверьте раздел [Troubleshooting](./TROUBLESHOOTING_RU.md)
2. Просмотрите логи: `docker compose logs -f`
3. Создайте issue в репозитории проекта

---

*Документация актуальна для версии 1.0.0*
