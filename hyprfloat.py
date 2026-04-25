import os
import json
import subprocess
from pathlib import Path
from socket import socket, AF_UNIX, SOCK_STREAM

SOCKET_PATH = f"{os.environ['XDG_RUNTIME_DIR']}/hypr/{os.environ['HYPRLAND_INSTANCE_SIGNATURE']}/.socket2.sock"
CONFIG_PATH = Path(__file__).parent / 'config.json'

with open(CONFIG_PATH) as f:
    config = json.load(f)

WINDOW_CLASSES = config["window_classes"]
FLOAT_WIDTH = config["float_size"]["width"]
FLOAT_HEIGHT = config["float_size"]["height"]
FLOAT_CLOSE = config.get("float_close", True)

def hyprctl(cmd):
    subprocess.run(['hyprctl'] + cmd, capture_output=True)

def get_clients():
    return json.loads(subprocess.run(['hyprctl', 'clients', '-j'], capture_output=True, text=True).stdout)

def is_matching_window(window):
    return window.get('class') in WINDOW_CLASSES

def workspace_matches(window, workspace):
    workspace = str(workspace)
    window_workspace = window.get('workspace', {})
    return str(window_workspace.get('id')) == workspace or window_workspace.get('name') == workspace

def is_special_workspace(window):
    workspace = window.get('workspace', {})
    return workspace.get('id', 0) < 0 or str(workspace.get('name', '')).startswith('special:')

def is_visible_workspace_window(window):
    return window.get('mapped', True) and not window.get('hidden', False) and not is_special_workspace(window)

def can_fullscreen(window):
    return not window.get('floating', False) or is_matching_window(window)

def has_fullscreen_capable_window(windows, ignored_address):
    return any(window['address'] != ignored_address and can_fullscreen(window) for window in windows)

def get_windows(workspace, class_filter=None):
    windows = [c for c in get_clients() if workspace_matches(c, workspace) and is_visible_workspace_window(c)]
    if class_filter:
        windows = [w for w in windows if w['class'] == class_filter]
    return windows

def get_client(address):
    for client in get_clients():
        if client['address'] == address:
            return client
    return None

def get_matching_windows(workspace):
    return [window for window in get_windows(workspace) if is_matching_window(window)]

def float_window(address):
    hyprctl(['dispatch', 'setfloating', f'address:{address}'])
    hyprctl(['dispatch', 'resizewindowpixel', 'exact', str(FLOAT_WIDTH), str(FLOAT_HEIGHT), f',address:{address}'])
    hyprctl(['dispatch', 'centerwindow', f',address:{address}'])

def tile_window(address):
    hyprctl(['dispatch', 'settiled', f'address:{address}'])

with socket(AF_UNIX, SOCK_STREAM) as sock:
    sock.connect(SOCKET_PATH)
    while True:
        event = sock.recv(1024).decode().strip()
        if not event:
            continue

        if event.startswith('openwindow>>'):
            data = event.split('>>')[1].split(',')
            if len(data) >= 3 and data[2] in WINDOW_CLASSES:
                address = f'0x{data[0]}'
                event_workspace = data[1]
                client = get_client(address)
                workspace = client['workspace']['name'] if client else event_workspace
                all_windows = get_windows(workspace)
                matching_windows = get_matching_windows(workspace)

                if has_fullscreen_capable_window(all_windows, address):
                    for window in matching_windows:
                        tile_window(window['address'])
                else:
                    float_window(address)
            else:
                data = event.split('>>')[1].split(',')
                if len(data) >= 2:
                    address = f'0x{data[0]}'
                    event_workspace = data[1]
                    client = get_client(address)
                    if client and not client.get('floating', False):
                        workspace = client['workspace']['name'] if client else event_workspace
                        all_windows = get_windows(workspace)
                        matching_windows = get_matching_windows(workspace)
                        if len(all_windows) > 1 and len(matching_windows) > 0:
                            for window in matching_windows:
                                tile_window(window['address'])
        
        elif event.startswith('closewindow>>'):
            workspace = json.loads(subprocess.run(['hyprctl', 'activeworkspace', '-j'], capture_output=True, text=True).stdout)
            workspace_name = workspace.get('name', workspace['id'])
            all_windows = get_windows(workspace_name)
            matching_windows = get_matching_windows(workspace_name)

            if FLOAT_CLOSE and len(all_windows) == 1 and len(matching_windows) == 1:
                float_window(matching_windows[0]['address'])
