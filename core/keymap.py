"""Key rows and Win32 virtual-key codes — shared by the GUI (labels)
and the hotkey daemon (RegisterHotKey), so the two can never drift."""

KEY_ROWS: dict[str, list[str]] = {
    "fkeys":  ["F1", "F2", "F3", "F4", "F5", "F6",
               "F7", "F8", "F9", "F10", "F11", "F12"],
    "numrow": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "="],
    "numpad": ["num1", "num2", "num3", "num4", "num5", "num6",
               "num7", "num8", "num9", "num0", "num.", "num+"],
    "qwerty": ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "[", "]"],
}

# label -> Win32 virtual-key code
VIRTUAL_KEYS: dict[str, int] = {
    **{f"F{n}": 0x70 + n - 1 for n in range(1, 13)},
    **{str(d): 0x30 + d for d in range(10)},
    "-": 0xBD, "=": 0xBB,                       # VK_OEM_MINUS, VK_OEM_PLUS
    **{f"num{d}": 0x60 + d for d in range(10)},
    "num.": 0x6E, "num+": 0x6B,                 # VK_DECIMAL, VK_ADD
    **{c: ord(c.upper()) for c in "qwertyuiop"},
    "[": 0xDB, "]": 0xDD,                       # VK_OEM_4, VK_OEM_6
}

# selector -> RegisterHotKey modifier flags (MOD_ALT=1, MOD_CONTROL=2, MOD_SHIFT=4)
MODIFIER_FLAGS: dict[str, int] = {
    "shift": 0x4,
    "ctrl": 0x2,
    "ctrl+shift": 0x6,
    "alt+shift": 0x5,
    # "hypershift" is handled by Razer Synapse via slot files, never here
}

MOD_NOREPEAT = 0x4000
