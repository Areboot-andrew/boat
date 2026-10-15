# Pi04 — перевірена конфігурація 15.10.2026

Це знімок конфігів конкретної Raspberry, не повний образ ОС і не дозвіл запускати рух. Не застосовувати до інших бортів. Паролі, ключі, координати, маршрути й сесії не включені. Дані перевірки — разовий стан, не гарантія подальшого зв'язку.

## Адреси QGC

- Comm Links → TCP: `100.68.157.23`, port `14551` — власна Battery10 телеметрія, не канал керування польотником.
- Камера 1: `rtsp://100.68.157.23:8554/cam1` (H.265); H.264: `rtsp://100.68.157.23:8554/cam1web`.
- Камера 2: **`rtsp://100.68.157.23:8554/cam2web`** (H.264). `cam2` існує в конфігу, але перевірка 15 секунд завершилася таймаутом; не вважати справним.
- Веб: http://100.68.157.23:8090/ . Tailscale на наземці потрібен. UDP push на наземку не налаштовувався: власник обрав RTSP pull.

## Що перевірено

| Вузол | Результат |
|---|---|
| GPS | USB/link OK; позиція та курс недоступні, fix=0, INSUFFICIENT_OBS/NONE, кількість супутників не повідомлена |
| Поправка курсу | -90° збережена без зміни; фізично не перевірена |
| BMS | Дані свіжі: приблизно 72,88 В, 54%, 0 А, 20 комірок; різниця близько 1 мВ |
| BMS alarm | Маска 4718592 ненульова, значення не розшифроване; не стверджувати «тривог немає» |
| Польотник | USB/HEARTBEAT свіжий, DISARMED/HOLD, MAV_STATE=5 CRITICAL; раніше повідомляв Radio Failsafe |
| Керування | Служба enabled/active; сесії немає, намір та застосовані команди нульові. Фізичний рух не тестувався |
| Відео | cam1/cam1web/cam2web віддали пакети ffprobe; обидві камери раніше візуально підтверджені LIVE у вебі |
| Автомісія / витрата на км | Не готові: немає GPS-позиції/курсу та даних руху. Значення запасу ходу не вигадуються |
| Raspberry | Близько 40°C, undervoltage/throttling=0, приблизно 22 ГіБ вільно; мережевих RX/TX помилок не видно |
| Інтернет / Tailscale | Працюють; TCP telemetry з ПК раніше отримано 185 байтів MAVLink2 |

Діагностика все ще показує GROUNDSTATION_OFFLINE та inactive harpoon-cam2-qgc-udp: UDP push не використовується, тому ці попередження самі по собі не доводять поломку RTSP. Політики CRITICAL не змінювалися: manual_critical_allowed=false, autonav_critical_allowed=false.

## Файли та призначення

П'ять файлів зчитані з live Pi04; `deployment.json` — довідкова структура, службами автоматично не читається.

| Файл | Live шлях |
|---|---|
| pi5-mediamtx.yml | /etc/harpoon/pi5-mediamtx.yml (JSON-сумісний YAML) |
| cam2.sdp | /etc/harpoon/cam2.sdp |
| camera_worker.py | /opt/harpoon/config/camera_worker.py |
| 60-pi04-usb.conf | /etc/systemd/system/harpoon-gps-monitor.service.d/60-pi04-usb.conf |
| 60-tail-telemetry.conf | /etc/systemd/system/harpoon-bms-mavlink.service.d/60-tail-telemetry.conf |

Worker імпортує встановлений config_model і читає boat.applied.json. Це не самодостатній інсталятор. Не перезаписувати існуючі camera-secrets.json, boat.json, ключі, маршрути чи GPS-monitor цілком.

## Внесені поправки

1. У камері 2 stream_main виправлено з 192.168.1.50:5600 на 192.168.10.50:5600.
2. WebRTC використовує тільки числові адреси LAN/Tailscale. Нерозпізнане harpoon-pi5-04.local зривало WHEP.
3. Live /opt/harpoon-bootstrap/refresh-tail.py також більше не додає hostname.local і DNSName до WebRTC hosts. SFTP читання цього системного скрипту заборонене: файл не експортували й права не змінювали. При майбутньому provisioning відтворити цю логіку; не повертати старий helper.
4. Лише cam2/udp у camera_worker.py: початковий analyzeduration=3000000, -copyinkf, -bsf:v dump_extra=freq=all. Це час стартового аналізу, не навмисна трисекундна затримка відтворення. Після зміни з'явилися raw H.265 та web H.264 потоки.

Загальні sources/config і старий provision payload не перегенеровані цим snapshot. Не називати їх ідентичними live Pi04.

## Відкат

На Pi04 збережені root-only backups:
- /var/backups/harpoon-pi04-commission-20261015.bvprnj2o
- /var/backups/harpoon-camera2-destination-20261015.ba17wxdi
- /var/backups/harpoon-pi04-webrtc-hosts-20261015.o4hhrxel
- /var/backups/harpoon-pi04-cam2-worker-20261015.5b14z95g

Відкочувати лише потрібні файли після порівняння. Відеопоправки потребують рестарту лише harpoon-pi5-camera. Перезапуск контролера — тільки після свіжого DISARMED/без сесії/нульових команд. Параметри польотника не змінювати. Команди ARM/серво/тяги агент під час цієї перевірки не надсилав.
