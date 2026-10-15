# HARPOON — Raspberry vessel dashboard and control

Вебінтерфейс водного транспорту: камери, GPS/курс, BMS, MAVLinkтелеметрія для QGC, ручне керування через USBпольотник і маршрутна навігація на RaspberryPi.

## Почати тут

- [AGENTS.md](AGENTS.md) — обов'язкові правила агента та межі дозволених дій.
- [PROJECT-MAP.md](PROJECT-MAP.md) — актуальне розташування компонентів і статус цієї копії.
- [PROJECT-GUIDE.md](PROJECT-GUIDE.md) — докладний опис архітектури, файлів, API, перевірок.
- [DEPLOYMENT.md](DEPLOYMENT.md) — збірка, перевірка, встановлення й відкат.

Це очищений експорт актуальних джерел від15.10.2026, **не образSD і не підтвердження готовності човна до руху**. Паролі, SSH/Tailscaleключі, журнали поїздок, SDбекапи, старі архіви та чужий starter не включені. Джерела історичного STM32/Arduinoпроєкту сюди не зливалися.

## Основні папки

| Папка | Вміст |
|---|---|
| `clones/harpoon-03/pilot-beta/` | Спільний актуальний код UI, керування, навігації й тести |
| `clones/harpoon-02/latest-20261014/build.py` | Генератор28файлового пакета дляPi01–Pi04 |
| `sources/monitor-assets/` | Версійовані HTML/JS/CSSресурси для збірки |
| `sources/gps-ui/` | Базові джерела GPS/BMSмонітора; для нового обладнання потрібна адаптація |
| `sources/bms-mavlink/` | Власна Battery10телеметрія, TCP/UDP |
| `sources/config/` | Генератор конфігів; перевіряти liveпараметри перед застосуванням |
| `tools/deploy/` | Відібрані guardedінструменти останнього оновлення |
| `config/` | Шаблон параметрів розгортання без секретів |

Історичні назвиPi03/Pi02 збережено, щоб не зламати розташування файлів. Це не дозвіл копіювати конфіги між бортами.

## Перевірка

Node.js потрібний дляJS mockтестів; Python3.11+ і Linux — для тестів контролера.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
node clones/harpoon-03/pilot-beta/test-live.cjs
node clones/harpoon-03/pilot-beta/test-pad.cjs
node clones/harpoon-03/pilot-beta/test-switch-start.cjs
node clones/harpoon-03/pilot-beta/test-route-editor.cjs
cd clones/harpoon-03/pilot-beta
python -m unittest test_manual_critical test_network_recovery test_audit_fixes test_autonav test_smooth
```

Ці тести не відкривають реальнийUSB. Не запускати `control_runner.py` як main для тесту на підключеному борту.

## Збірка без розгортання

З кореня:

```sh
python clones/harpoon-02/latest-20261014/build.py 1
```

Аргумент1–4 обирає boardадаптацію. Результат — `clones/harpoon-0N/latest-20261014/latest-app.tar.gz` і manifest. У цій Gitверсії assets беруться з `sources/monitor-assets`, а не приватного provisionpayload. Пакет оновлює застосунок, але не є повним інсталяторомOS/камер/залежностей; див.DEPLOYMENT.md.

## Обмеження

- Не змінювати польотник без окремого явного дозволу власника. Завантаження репозиторію не дозволяє ARM/рух/перепрошивання.
- Після3секунд без команд чинна логіка обнуляє виходи, залишає сесію та скасовує місію. Відновлення місії — оператором.
- Автомісія потребує достовірної позиції та курсу, не має виявлення перешкод. Повернення по записаному треку відрізняється від плавного маршруту редактора.
- Новий autonav потребує heading_age_s/speed_age_s/position_age_s від GPSмонітора.
- НаPi04контролер був disabled, його не активувати автоматично.
- Перед реальним використанням потрібні перевірка конкретного обладнання й контрольовані випробування.

Сторонні компоненти: [THIRD-PARTY.md](THIRD-PARTY.md). Ця публікація сама по собі не призначає нову ліцензію власному коду.
