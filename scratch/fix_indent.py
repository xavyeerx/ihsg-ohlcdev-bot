import sys

file_path = r"d:\ALGO TRADE\ihsg-supertrend-scanner\ihsg-ohlcdev-bot\core\engines.py"
with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []

for line in lines:
    lstripped = line.lstrip()
    indent = line[:len(line)-len(lstripped)]
    
    # Any commented line that has multiple spaces after '#' was likely an indented code block
    if lstripped.startswith("#     ") or lstripped.startswith("#         ") or lstripped.startswith("#             "):
        # Remove the first two characters '# ' to restore the original indentation
        uncommented = indent + lstripped[2:]
        new_lines.append(uncommented)
    else:
        new_lines.append(line)

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Done fixing indentation errors in core/engines.py")
