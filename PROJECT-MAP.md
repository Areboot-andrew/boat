# HARPOON — карта публічного репозиторію

## Pi04: оновлення 15.10.2026

Див. [config/pi04/README.md](config/pi04/README.md) та deployment.json: live-конфіги камер, GPS/BMS USB, TCP Battery10 через 100.68.157.23:14551, перевірені RTSP-посилання й обмеження. Контролер Pi04 тепер ввімкнений за окремим дозволом власника; нижній запис disabled стосується 14.10. GPS без fix/курсу, FC CRITICAL; готовність до руху не підтверджена. Нові camera_worker/WebRTC поправки збережені окремо для Pi04, не поширені автоматично на інші борти або загальний provision payload.

Оновлено15.10.2026. Спочатку читатиAGENTS.md. Репозиторій https://github.com/Areboot-andrew/boat містить очищений експорт, а не повну локальну історію чи liveобрази.

## Поточний стан коду

Канонічне джерело `clones/harpoon-03/pilot-beta/` містить виправлення immediateSTOP, neutralresync після втрати auto_startACK, локальний10Гцnavloop, combinedGPSages, debounceAxis6. Локально ці зміни були встановлені наPi01–Pi04; це історія14.10, не доказ поточного стану обладнання.

Pi01/Pi02/Pi03 під час останньої перевірки мали активний контролер; Pi04 залишена disabled. Будь-який статусARM/зв'язку треба читати заново. Паролі та оперативні логи не входять уGit.

## Розташування

- UI/control/nav: `clones/harpoon-03/pilot-beta/`.
- Boardпакети: `clones/harpoon-02/latest-20261014/build.py`, аргументи1–4; генерує в папкувідповідногоборта.
- GPS/BMSbaseline: `sources/gps-ui/`; GPSпорт навмисноunconfigured, agefieldsдодані. Перед використанням звіряти headingoffset, порти, serviceEnvironment і код із конкретним бортом; не переписувати livegpsмонітор цілком.
- Battery10MAVLink: `sources/bms-mavlink/`, sys1/comp191; неUSBретранслятор.
- Камери: `sources/config/` і monitorassets; фактичний codec/UDP/RTSPpipeline перевіряти на борту. БінарникиMediaMTX/FFmpeg не включені.
- Diagnostics: `clones/harpoon-02/diagnostics/`.
- Guardedupdate: `tools/deploy/`, використовується з окремо знятими livebaselineархівами, які не публікуються.

## Відмінності від приватного workspace

Старі `work/` скрипти відібрані в `tools/deploy/`. ПриватнийPROJECT-MAP з адресними журналами/backupісторією замінений цією короткою картою. ACCESS-LOCAL.private.md, HANDOFF-UA.md, образи, SDuser-data, журнали та приватніключі виключені. Vinextstarter і DesktopHARPOON(STM32/Arduino) не включені.

Генератор більше не потребує `clones/provision/payload.tar.gz` дляHTML/JS/CSS. ПовнийfreshOSprovisioner ще не перенесений: не вважати цей checkoutготовим образом клону. Для відновлення liveборта потрібні його приватніконфіги, доступи та обраний backup.

## Правила зміни

Передremotewrite — pinnedhostkey +hostname, backup, старіхеші, idleDISARMED дляконтролера. Не мінятиFCпараметри/прошивку/калібрування. Окремо перевіряти сервоmapping, GPSoffset, джерелакамер, наземкуQGC. Тести й обмеження записувати в commit/documentation. Не додавати секрети навіть уprivatebranch.
