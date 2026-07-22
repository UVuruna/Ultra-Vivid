"""Available shortcut keys and Win32 virtual-key codes — shared by the
GUI (key picker) and the hotkey daemon (RegisterHotKey), so the two can
never drift. The user picks ANY combination of these keys for a set."""

# label -> Win32 virtual-key code
VIRTUAL_KEYS: dict[str, int] = {
    **{f"F{n}": 0x70 + n - 1 for n in range(1, 13)},
    **{str(d): 0x30 + d for d in range(10)},
    "-": 0xBD, "=": 0xBB,                       # VK_OEM_MINUS, VK_OEM_PLUS
    **{f"num{d}": 0x60 + d for d in range(10)},
    "num.": 0x6E, "num+": 0x6B, "num-": 0x6D,   # VK_DECIMAL, VK_ADD, VK_SUBTRACT
    "num*": 0x6A, "num/": 0x6F,                 # VK_MULTIPLY, VK_DIVIDE
    **{c: ord(c.upper()) for c in "abcdefghijklmnopqrstuvwxyz"},
    "[": 0xDB, "]": 0xDD,                       # VK_OEM_4, VK_OEM_6
    ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF, "`": 0xC0,
}

# GUI key-picker groups (display only — any mix of keys goes in one set)
KEY_GROUPS: dict[str, list[str]] = {
    "Function keys": [f"F{n}" for n in range(1, 13)],
    "Number row": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "="],
    "Numpad": ["num1", "num2", "num3", "num4", "num5", "num6", "num7",
               "num8", "num9", "num0", "num.", "num+", "num-", "num*", "num/"],
    "Letters": list("qwertyuiop") + ["[", "]"] + list("asdfghjkl") + [";", "'"]
               + list("zxcvbnm") + [",", ".", "/", "`"],
}

# selector -> RegisterHotKey modifier flags (MOD_ALT=1, MOD_CONTROL=2, MOD_SHIFT=4)
MODIFIER_FLAGS: dict[str, int] = {
    "shift": 0x4,
    "ctrl": 0x2,
    "alt": 0x1,
    "ctrl+shift": 0x6,
    "alt+shift": 0x5,
    "ctrl+alt": 0x3,
    # "hypershift" is handled by Razer Synapse via slot files, never here
}

MOD_NOREPEAT = 0x4000
