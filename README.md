# Instagram -> Telegram Funnel Bot

Backend на `FastAPI + python-telegram-bot + SQLite` и веб-админка на `Vue 3 + Vite`.

## Что реализовано

- сегментация входящего трафика по 3 направлениям;
- интерактивная выдача micro-value внутри Telegram;
- tripwire offer и фиксация конверсии;
- логирование каждого действия пользователя в БД;
- fallback на неверный текстовый ввод;
- антиспам-ограничение;
- цепочка follow-up сообщений на 72 часа;
- редактор шагов воронки;
- автоматизации по бездействию и выдача бонусов;
- финальный шаг оплаты через Platega;
- веб-админка для аналитики, шагов, автоматизаций, сегментов, пользователей, событий и настроек копирайта.

## Запуск backend

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python main.py
```

API будет доступен на `http://127.0.0.1:8000`.

## Запуск frontend

```powershell
cd frontend
npm install
npm run dev
```

Админка будет доступна на `http://127.0.0.1:5173`.

## Что ещё стоит добавить под прод

- JWT/admin sessions вместо basic auth;
- экспорт аналитики, UTM и deep-link tracking;
- рассылки из админки с очередями;
- CDN/media storage для видео-кейсов;
- webhook режим Telegram вместо polling;
- callback/webhook от Platega для автоматического подтверждения успешной оплаты.
