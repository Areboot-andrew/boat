# HARPOON — опис проєкту та карта коду

**Уточнення для публічного експорту:** нижче збережений опис приватного workspace. У цьому checkout вибраніскрипти зwork перенесені в `tools/deploy/`, assets — у `sources/monitor-assets/`; boardbuilderперевіренийбезстарогопayload. Vinextstarter, приватнийHANDOFF і GIT-READINESS не включені. ПовнийfreshOSinstaller не включений. Актуальні дляцьогоcheckoutкроки — README.md і DEPLOYMENT.md.

Репозиторій призначення: https://github.com/Areboot-andrew/boat.git

Актуальність опису: 15.10.2026. Це навігатор; поточний стан пристроїв перевіряється окремо. Перед роботою читати `AGENTS.md` і `PROJECT-MAP.md`.

## Що це

Система вебкерування водним транспортом на RaspberryPi: дві камери, GPS/курс, BMS, власна MAVLinkтелеметрія до QGC, ручне керування через USBпольотник та маршрутна навігація. Pi01–Pi04 — різні пристрої, не взаємозамінні конфіги.

| Частина | Потік даних |
|---|---|
| Веб8090 | Браузер → sameoriginproxy → локальний controlAPI8091 → USBMAVLink |
| GPS/BMS | Пристрої → gps-ui → HTTP8080/telemetry → веб і обчислення |
| QGC Battery10 | HTTP8080 → bms-mavlink → TCP14551 / окремий UDPsender |
| Камери | RTSP/UDPкамер → FFmpeg/MediaMTX → веб або QGC |
| Автомісія | Збережені точки + GPS/курс → follower на Raspberry → спільний шлях виходів |

Власна Battery10телеметрія — system1/component191. Вона не ретранслює польотник і не є каналом керування. На кількох бортах ці ID однакові — не зливати потоки в одну сесію QGC без окремого рішення.

## Файли

Спільний вихідний код — `clones/harpoon-03/pilot-beta/`:

| Файл | Призначення |
|---|---|
| control_service.py, fc_usb.py | Сесії, USBвибір, MAVLink, freshness, виходи |
| control_runner.py | Boardадаптація, APIдії, локальний цикл автомісії |
| autonav.py | Валідація GPS, налаштування, траєкторія, регулятор |
| live-control.js | Клавіатура, сесії, STOP, відновлення зв'язку |
| pad-config.js | TX12, осі, калібрування, перемикачі ліміту |
| server.py, control_proxy.py | Вебсервер і sameoriginproxy; ключ не передається браузеру |
| beta.js/css | Розкладка, камери/PiP, панелі |
| navigation.js/css, voyage.py | Прилади, навігація й історія поточної поїздки |
| route-editor.js/css, auto-ui.css | Точки, плавна лінія, налаштування й запуск |
| test_*.py, test-*.cjs | Ізольовані регресійні тести |

`clones/harpoon-01/`…`harpoon-04/` містять власніSSHпомічники, артефакти й історію. `clones/provision/` — підготовка чистоїOS, але payload потребує оновлення після останніх змін. `app/`, `worker/`, `db/` — інший starter, не liveсервер борта.

## На Raspberry

| Шлях / служба | Призначення |
|---|---|
| /opt/harpoon/web-control, harpoon-web-control | Контролер і API8091, лишеloopback |
| /opt/harpoon/pilot-beta | Веб8090 наPi01/Pi03/Pi04 |
| /opt/harpoon/pilot | Веб8090 наPi02 |
| /opt/harpoon/gps-ui, harpoon-gps-monitor | GPS/BMSHTTP8080 |
| /opt/harpoon/bms-mavlink, harpoon-bms-mavlink | TCPвласної телеметрії |
| /etc/harpoon | Окремі liveконфіги, не копіювати між бортами без звірки |
| /var/lib/harpoon-autonav | Налаштування й маршрут |
| /var/lib/harpoon-pilot-nav | Стан навігації/поїздки |
| /var/backups | Точкові резервні копії розгортань |

Конкретні адреси, hostkeys, поправки й останні backupшляхи — у локальній карті проєкту/журналі борта. Паролі — тільки приватно поза Git, ніколи не вписувати сюди.

## Розробка й перевірка

З кореня репозиторію, за наявності Node.js:

```sh
node clones/harpoon-03/pilot-beta/test-live.cjs
node clones/harpoon-03/pilot-beta/test-pad.cjs
node clones/harpoon-03/pilot-beta/test-switch-start.cjs
node clones/harpoon-03/pilot-beta/test-route-editor.cjs
```

Linux, ізольоване Pythonсередовище з pymavlink, без запуску живої служби:

```sh
cd clones/harpoon-03/pilot-beta
python -m unittest test_manual_critical test_network_recovery test_audit_fixes test_autonav test_smooth
```

Частина unittestвиконує успадковані сценарії повторно; кількість виконань не означає стільки ж незалежних тестів. Mockтести не підтверджують фізичну роботу човна чи якість Starlink.

## Збірка і встановлення — різні етапи

```sh
python clones/harpoon-02/latest-20261014/build.py 1
```

Аргумент1–4 обирає борт. Команда готує пакет/manifest, нічого не встановлює. Вона використовує існуючий provisionpayload для monitorassets; чистий checkout без цього payload наразі не є самодостатньою збіркою. Перед публікацією треба винести перевірені assets у версійовані джерела, не завантажувати старий архів навмання.

Останній безпечний updater знаходиться в локальному ignoredwork (`build-auditfix.py`, `install-auditfix.py`, `auditfix-verify.sh`); він перевіряє oldhash, backup, hostname та DISARMED/idle. Перед перенесенням у Git потрібен окремий відбір інструментів. Наявність коду чи пакета не означає, що він установленний на всіх бортах.

## Що не забути

- Не змінювати польотник під час робіт із Raspberry/web.
- Pi04контролер не вводився в експлуатацію; disabledстан зберігати.
- GPSpositionvalid недостатньо: потрібен свіжий достовірний курс. Не підміняти його випадковим courseна стоянці.
- STOP, nonce/sequence, мережеве відновлення, осіTX12 — взаємопов'язана логіка; зміни перевіряти регресійними тестами.
- Поточний3snetworktimeout не гарантує безперервний рух без зв'язку; місія потребує повторного запуску після паузи.
- Повернення записаним треком не має повної smoothгеометрії редактора; автоматичного виявлення перешкод немає.
- DesktopHARPOON — окремий старіший STM32/Arduinoпроєкт, не актуальна копія цього дерева.

## Публікація

Рекомендується приватний репозиторій. Виключити секрети, SDобрази/бекапи, телеметричні сесії, приватні координати та старі архіви. Не копіювати всю робочу папку або її .gitісторію до перевірки. Див. локальний `GIT-READINESS-20261015.md`.
