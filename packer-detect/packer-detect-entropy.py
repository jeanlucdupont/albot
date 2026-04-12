import pefile
import math
import os
import sys

def shannon_entropy(data):
    if len(data) == 0:
        return 0

    entropy = 0
    for x in range(256):
        p_x = float(data.count(x)) / len(data)
        if p_x > 0:
            entropy += -p_x * math.log2(p_x)
    return entropy

def analyze_file(filepath):
    try:
        pe = pefile.PE(filepath)
        for section in pe.sections:
            entropy = shannon_entropy(section.get_data())
            if entropy > 6.9:
                filename = os.path.basename(filepath)
                print(f"[!] {filename} -> High entropy: {section.Name.decode(errors='ignore').strip()} ({entropy:.2f})")
    except Exception as e:
        # Skip non-PE or unreadable files
        pass

def scan_directory(root_dir):
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith((".exe", ".bin_exe", ".dll", ".exe_")):
                full_path = os.path.join(root, file)
                analyze_file(full_path)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <directory>")
        sys.exit(1)

    target_dir = sys.argv[1]
    scan_directory(target_dir)
