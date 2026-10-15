# Розгортання без втрати конфігів

Ці інструменти оновлюють існуючу встановлену систему, не готують чистуOS. Нічого не розгортати автоматично після clone/pull.

1. ПрочитатиAGENTS.md і визначити борт.
2. Перевірити hostkey/hostname через відповідний SSHпомічник. Пароль передається через HARPOON_SSH_PASSWORD з приватного локального джерела, не аргументомкоманди й неGitфайлом. Потрібен встановлений paramiko.
3. Прочитати `tools/deploy/auditfix-read.sh` перед запуском. Скрипт знімає6файловий baseline; він не вмикаєкерування. Завантажити його локально до ignored`work/pi0N-auditfix-baseline.tar.gz`.
4. Виконати `python tools/deploy/build-auditfix.py N`. Він генерує пакет під поточнийbaseline, змінює5файлів застосунку й додає2agefields у власнийgpsmonitor. Якщоagefieldsвжеє — assert зупиняєповторнеоновлення: не прибирати guardнавмання.
5. Mockтести запускати ізольовано. Перед liveinstall потрібен свіжийDISARMED/no lease/zerointent+applied або збереженняdisabledконтролера. ОператорDISARM — не агент без окремоїкоманди.
6. ПеревіритиSHAпакета, завантажити у/tmp і прочитаний `install-auditfix.py`. Інсталятор приймає boardномер іSHA256, перевіряє6oldhashes, створюєbackup, зберігаєконфіги та попереднійстанслужб. Не запускаєdisabledконтролер.
7. Перевірити `auditfix-verify.sh`, HTTPservedhashes, journals, GPSages, freshUSB. ПіслязавершеннячитанняRCпараметрів повторитиreadinesscheck.
8. Перезавантажувати браузер тількиколиоператорне керує.

Дляrollback використатиbackup самецьогобортапісляDISARM/idle, повернути6файлів іперезапустити лише ранішепрацюючіслужби. Не відновлюватипаролі/Tailscaleidentity чи файли іншогоборта.

## Телеметрія

TCPсервіс читаєлокальнийHTTP8080, видаєHeartbeat/BATTERY_STATUSID10/NAMED_VALUE_FLOAT. Віннеприймаєкомандпольотнику. Env: BMS_TCP_BIND, BMS_TCP_PORT. QGCпідключаєтьсяTCPклієнтом. UDPsenderокремий: BMS_QGC_HOST/PORT.

`pi03-tail-telemetry-*` — історичнийточковийinstallerPi03 з жорсткоюперевіркоюhostname/IP івідмовоюякщоoverrideвжеіснує. Це неуніверсальнаналаштовувалка; прочитатипередвикористанням. Firewall/TailscaleACL/sharing тутне змінюються.

## Секрети

`config/deployment.example.json` — довідковийшаблон, неавтоматичнийконфігсервісу. Заповненийоперативнийфайл зберігати позаGit. Не копіюватиSDобраз,tailstate,keys,sessionDB або user-data уrepo.
