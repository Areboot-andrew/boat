import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('diag',Path(__file__).with_name('harpoon-diagnostics.py'))
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
healthy={'undervoltage_now':False,'throttled_now':False,'temperature_c':40,
'memory_kib':{'MemAvailable':1000000,'MemTotal':2000000},'disk_free_mib':10000,'root_readonly':False,
'interfaces':{'eth0':{'carrier':'1'}},'network':{'gateway':'192.168.10.1','internet_tcp_443':{'a':True},'dns_ok':True,'tailscale':{'state':'Running','self_online':True},'groundstation_online':True},
'camera2_udp':{'age_s':0.1,'error':None},'telemetry_error':None,'gps':{'link_ok':True,'position_valid':True},'bms':{'link_ok':True},'services':{'test':{'ActiveState':'active'}}}
assert d.problems(healthy)==[]
assert 'POWER_UNDERVOLTAGE' in d.problems({**healthy,'undervoltage_now':True})
assert 'CAMERA2_NO_UDP' in d.problems({**healthy,'camera2_udp':{'age_s':None,'error':None}})
assert 'MEMORY_LOW' in d.problems({**healthy,'memory_kib':{'MemAvailable':10000,'MemTotal':2000000}})
assert 'ROOT_READONLY' in d.problems({**healthy,'root_readonly':True})
assert 'GPS_NO_FIX' in d.problems({**healthy,'gps':{'link_ok':True,'position_valid':False}})
print('6 diagnostic classification tests passed')
from unittest.mock import patch
def logged_out_command(args,timeout=4):
    if args[0]=='tailscale':return 0,'{"BackendState":"NeedsLogin","Self":null,"Peer":null,"Health":null}'
    if args[0]=='ip':return 0,'[]'
    return 1,''
with patch.object(d,'command',side_effect=logged_out_command),patch.object(d,'read',return_value='10 0'),patch.object(d.socket,'create_connection',side_effect=OSError('offline')):
    net=d.network()
    assert net['tailscale']['state']=='NeedsLogin' and net['tailscale']['self_online'] is None
    assert net['groundstation_online'] is None
print('Logged-out Tailscale null fields regression passed')
