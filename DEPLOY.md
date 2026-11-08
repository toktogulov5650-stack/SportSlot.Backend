# Размещение на Google Cloud Run

Проект Google Cloud: `ecobilling-karakulja` (оплата уже подключена, Cloud Run включён).
Сервис называется `sportslot-api`. База данных: бесплатный PostgreSQL (Neon).

## 1. Создать базу данных (один раз)

1. Откройте https://neon.tech и зарегистрируйтесь.
2. Создайте проект. Регион выберите ближайший: **AWS Europe (Frankfurt)**.
3. На странице проекта нажмите **Connect** и скопируйте строку подключения. Она выглядит так:
   `postgresql://пользователь:пароль@хост/neondb?sslmode=require`

Эту строку нельзя никому показывать и нельзя выкладывать в интернет: это пароль от базы.

## 2. Задеплоить сервер

Откройте PowerShell в папке `D:\SportSlot.Backend`.

Сначала сгенерируйте секретный ключ Django:

```bash
.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(50))"
```

Затем запустите деплой (вместо `КЛЮЧ` и `СТРОКА_ИЗ_NEON` вставьте свои значения):

```bash
gcloud run deploy sportslot-api --project ecobilling-karakulja --source . --region europe-west3 --allow-unauthenticated --set-env-vars "^@^DEBUG=0@SEED_DEMO=1@SECRET_KEY=КЛЮЧ@DATABASE_URL=СТРОКА_ИЗ_NEON"
```

* `--source .` — Google сам соберёт контейнер по `Dockerfile`, Docker на компьютере не нужен;
* `SEED_DEMO=1` — при первом запуске создаст тестовые аккаунты и площадки. После этого
  переменную можно убрать;
* `^@^` в начале — разделитель переменных `@`, чтобы запятые и `&` в строке базы ничего не ломали;
* `--allow-unauthenticated` — сервер открыт из интернета (вход в приложение защищён токеном).

Первый деплой занимает 3–5 минут. В конце gcloud напечатает адрес сервиса вида
`https://sportslot-api-xxxxxxxx-ew.a.run.app`. Если gcloud спросит про создание
репозитория Artifact Registry, ответьте `Y`.

## 3. Проверить

Откройте в браузере `<адрес>/api/venues/`. Должен прийти ответ
`{"detail":"Authentication credentials were not provided."}` — значит, сервер работает
и требует вход. Войти можно под `aibek@gmail.com` / `123456`.

## 4. Обновление

После любых изменений кода повторите команду деплоя. Переменные окружения
сохраняются, поэтому в следующие разы достаточно:

```bash
gcloud run deploy sportslot-api --project ecobilling-karakulja --source . --region europe-west3
```

## Что делают переменные окружения

| Переменная | Зачем |
|---|---|
| `DEBUG=0` | Выключает режим разработки (прячет подробные ошибки) |
| `SECRET_KEY` | Секретный ключ Django. У каждого проекта свой |
| `DATABASE_URL` | Адрес базы PostgreSQL. Если её нет, используется SQLite-файл |
| `SEED_DEMO=1` | Заполнить базу тестовыми данными при запуске |
| `ALLOWED_HOSTS` | Необязательно: список разрешённых адресов через запятую |
