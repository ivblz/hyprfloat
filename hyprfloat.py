import os
import json
import subprocess
from pathlib import Path
from socket import socket, AF_UNIX, SOCK_STREAM

SOCKET_PATH = f"{os.environ['XDG_RUNTIME_DIR']}/hypr/{os.environ['HYPRLAND_INSTANCE_SIGNATURE']}/.socket2.sock"
CONFIG_PATH = Path(__file__).parent / 'config.json'

with open(CONFIG_PATH) as f:
    config = json.load(f)

WINDOW_CLASSES = set(config["window_classes"])
FLOAT_WIDTH = config["float_size"]["width"]
FLOAT_HEIGHT = config["float_size"]["height"]
FLOAT_CLOSE = config.get("float_close", True)

def hyprctl(cmd):
    subprocess.run(['hyprctl'] + cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def get_clients():
    return json.loads(subprocess.run(['hyprctl', 'clients', '-j'], capture_output=True, text=True).stdout)

def is_matching_window(window):
    return window.get('class') in WINDOW_CLASSES

def normalize_address(address):
    return address if address.startswith('0x') else f'0x{address}'

def workspace_matches(window, workspace):
    workspace = str(workspace)
    window_workspace = window.get('workspace', {})
    return str(window_workspace.get('id')) == workspace or window_workspace.get('name') == workspace

def is_special_workspace(window):
    workspace = window.get('workspace', {})
    return workspace.get('id', 0) < 0 or str(workspace.get('name', '')).startswith('special:')

def is_special_workspace_name(workspace):
    return str(workspace).startswith('special:')

def is_visible_workspace_window(window, workspace):
    return window.get('mapped', True) and not window.get('hidden', False) and (is_special_workspace_name(workspace) or not is_special_workspace(window))

def has_tiled_window(windows, ignored_address):
    return any(window['address'] != ignored_address and not window.get('floating', False) for window in windows)

def index_clients(clients):
    return {client['address']: client for client in clients}

def float_lonely_matching_window(workspace, clients):
    if not FLOAT_CLOSE:
        return clients

    all_windows = get_windows(workspace, clients)
    matching_windows = [window for window in all_windows if is_matching_window(window)]
    if len(matching_windows) != 1:
        return clients

    address = matching_windows[0]['address']
    if not has_tiled_window(all_windows, address):
        for window in all_windows:
            if window['address'] != address:
                tile_window(window)

        clients = get_clients()
        all_windows = get_windows(workspace, clients)
        matching_windows = [window for window in all_windows if is_matching_window(window)]
        if len(matching_windows) != 1:
            return clients

    if has_tiled_window(all_windows, matching_windows[0]['address']):
        tile_window(matching_windows[0])
    else:
        float_window(matching_windows[0])

    return clients

def get_windows(workspace, clients):
    return [c for c in clients if workspace_matches(c, workspace) and is_visible_workspace_window(c, workspace)]

def get_client(address, clients_by_address):
    return clients_by_address.get(address)

def get_client_workspace(client):
    workspace = client.get('workspace', {})
    return workspace.get('name', workspace.get('id'))

def float_window(window):
    if window.get('floating', False):
        return

    address = window['address']
    hyprctl(['dispatch', 'setfloating', f'address:{address}'])
    hyprctl(['dispatch', 'resizewindowpixel', 'exact', str(FLOAT_WIDTH), str(FLOAT_HEIGHT), f',address:{address}'])
    hyprctl(['dispatch', 'centerwindow', f',address:{address}'])

def tile_window(window):
    if not window.get('floating', False):
        return

    hyprctl(['dispatch', 'settiled', f"address:{window['address']}"])

def settle_matching_window(window, workspace, clients):
    address = window['address']
    all_windows = get_windows(workspace, clients)

    if not has_tiled_window(all_windows, address):
        for other_window in all_windows:
            if other_window['address'] != address:
                tile_window(other_window)

        clients = get_clients()
        window = get_client(address, index_clients(clients))
        if not window:
            return clients

        all_windows = get_windows(workspace, clients)

    if has_tiled_window(all_windows, address):
        for matching_window in all_windows:
            if is_matching_window(matching_window):
                tile_window(matching_window)
    else:
        float_window(window)

    return clients

window_workspaces = {
    client['address']: get_client_workspace(client)
    for client in get_clients()
}

with socket(AF_UNIX, SOCK_STREAM) as sock:
    sock.connect(SOCKET_PATH)
    while True:
        event = sock.recv(1024).decode().strip()
        if not event:
            continue

        if event.startswith('openwindow>>'):
            data = event.split('>>')[1].split(',')
            clients = get_clients()
            clients_by_address = index_clients(clients)
            if len(data) >= 3 and data[2] in WINDOW_CLASSES:
                address = normalize_address(data[0])
                event_workspace = data[1]
                client = get_client(address, clients_by_address)
                workspace = get_client_workspace(client) if client else event_workspace
                window_workspaces[address] = workspace
                if client:
                    clients = settle_matching_window(client, workspace, clients)
            else:
                if len(data) >= 2:
                    address = normalize_address(data[0])
                    client = get_client(address, clients_by_address)
                    if client:
                        workspace = get_client_workspace(client)
                        window_workspaces[address] = workspace

                    if client and not client.get('floating', False):
                        all_windows = get_windows(workspace, clients)
                        matching_windows = [window for window in all_windows if is_matching_window(window)]
                        if len(all_windows) > 1 and len(matching_windows) > 0:
                            for window in matching_windows:
                                tile_window(window)

        elif event.startswith('movewindow>>') or event.startswith('movewindowv2>>'):
            data = event.split('>>')[1].split(',')
            clients = get_clients()
            clients_by_address = index_clients(clients)
            if len(data) >= 1:
                address = normalize_address(data[0])
                old_workspace = window_workspaces.get(address)
                client = get_client(address, clients_by_address)

                if client:
                    new_workspace = get_client_workspace(client)
                    window_workspaces[address] = new_workspace

                    if is_matching_window(client):
                        clients = settle_matching_window(client, new_workspace, clients)
                    elif not client.get('floating', False):
                        for window in get_windows(new_workspace, clients):
                            if not is_matching_window(window):
                                continue
                            tile_window(window)

                if old_workspace is not None:
                    clients = float_lonely_matching_window(old_workspace, clients)

        elif event.startswith('closewindow>>'):
            address = normalize_address(event.split('>>')[1])
            workspace_name = window_workspaces.pop(address, None)
            clients = get_clients()

            if workspace_name is None:
                workspace = json.loads(subprocess.run(['hyprctl', 'activeworkspace', '-j'], capture_output=True, text=True).stdout)
                workspace_name = workspace.get('name', workspace['id'])

            clients = float_lonely_matching_window(workspace_name, clients)
