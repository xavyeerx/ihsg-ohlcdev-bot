import sys

file_path = r"d:\ALGO TRADE\ihsg-supertrend-scanner\ihsg-ohlcdev-bot\core\engines.py"
with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip_next = False

for i, line in enumerate(lines):
    if skip_next:
        skip_next = False
        continue
    
    lstripped = line.lstrip()
    indent = line[:len(line)-len(lstripped)]
    
    # We target specific commented lines used for API requests and response handling
    target_prefixes = [
        "# raw = _get",
        "# if raw:",
        "# data = ",
        "# result.",
        "# return ",
        "# if result.hot_sectors:",
        "# for sector in ",
        "# sector_name = ",
        "# stocks = ",
        "# if isinstance",
        "# sectors = "
    ]
    
    if any(lstripped.startswith(prefix) for prefix in target_prefixes):
        # ensure we are only replacing the first "# "
        uncommented = indent + lstripped[2:]
        
        # if this is a 'return raw.get' we want to skip the next 'return None' if it's there
        if uncommented.strip().startswith("return ") and "raw.get" in uncommented:
            if i + 1 < len(lines) and lines[i+1].strip() == "return None":
                skip_next = True
        
        new_lines.append(uncommented)
    else:
        new_lines.append(line)

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Done uncommenting core/engines.py")
