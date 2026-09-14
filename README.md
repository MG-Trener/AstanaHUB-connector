# Astana Hub daily reward

Ежедневный вход в Astana Hub по email и паролю с получением награды. Сценарий запускается в приватном репозитории через GitHub Actions и не требует включённого пользовательского компьютера.

## Требование к аккаунту

Astana Hub должен разрешать вход по постоянному паролю. Если для email включён OTP, workflow остановится: одноразовый код нельзя получить автономно без отдельной интеграции с почтой.

## Настройка приватного репозитория

1. Создайте на GitHub пустой приватный репозиторий.
2. Загрузите в него этот проект.
3. Откройте `Settings → Secrets and variables → Actions`.
4. Создайте два repository secret:
   - `ASTANAHUB_EMAIL` — email аккаунта Astana Hub;
   - `ASTANAHUB_PASSWORD` — пароль аккаунта Astana Hub.
5. Откройте вкладку `Actions`, выберите `Astana Hub daily reward` и нажмите `Run workflow` для проверки.

Workflow запускается ежедневно в 18:00 UTC, то есть в 23:00 по времени Asia/Qyzylorda. GitHub может начать запланированное задание на несколько минут позже.

## Безопасность

Не добавляйте email и пароль в файлы проекта. Они передаются процессу только через GitHub Actions Secrets. Workflow имеет разрешение только на чтение содержимого репозитория.

Локальная проверка:

```powershell
$env:ASTANAHUB_EMAIL = "you@example.com"
$env:ASTANAHUB_PASSWORD = "your-password"
.\.venv\Scripts\python.exe main.py
```

