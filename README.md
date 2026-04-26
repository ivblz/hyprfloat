# Hyprfloat

[Hyprfloat](https://github.com/nevimmu/hyprfloat) didnt work for me, so i wrote my own version of it

### Clone the repo

```bash
git clone https://github.com/talyamm/hyprfloat
mv hyprfloat ~/.local/share/bin
```

### Then add it to autostart

```bash
exec-once = python ~/.local/share/bin/hyprfloat/hyprfloat.py &
```

## Config example

```bash
{
	"window_classes": ["kitty"],
	"float_size": {
		"width": 1400,
		"height": 1000
	}
}
```

( whole thing uses about 17MB btw )

All cases when the terminal is in a floating state:
1. The terminal is open on an empty regular workspace.
2. The terminal is open on the workspace, where all other windows have only a floating state.
3. The terminal has been moved to workspace, where all other windows have only a floating state.
4. After closing the window, there is only one terminal on the workspace, and there are no other tiled windows.
5. After moving the window from the old workspace, there is only one terminal left, and there are no other tiled windows.
6. There is only a terminal on the workspace, and the rest of the windows are in special:magic / scratchpad
