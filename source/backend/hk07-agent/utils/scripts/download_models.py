import os
import sys
import urllib.request

# Configuration
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")

MODELS = {
    "phi-3-mini-4k-instruct-q4.gguf": "https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf",
    "moondream2.gguf": "https://huggingface.co/moondream/moondream2-gguf/resolve/main/moondream2-text-model-f16.gguf",
    "moondream2-mmproj.bin": "https://huggingface.co/moondream/moondream2-gguf/resolve/main/moondream2-mmproj-f16.gguf"
}

def report_progress(block_num, block_size, total_size):
    read_so_far = block_num * block_size
    if total_size > 0:
        percent = min(100, (read_so_far * 100) / total_size)
        sys.stdout.write(f"\rDownloading... {percent:.2f}% ({read_so_far / (1024 * 1024):.2f} MB / {total_size / (1024 * 1024):.2f} MB)")
    else:
        sys.stdout.write(f"\rDownloading... ({read_so_far / (1024 * 1024):.2f} MB)")
    sys.stdout.flush()

def main():
    os.makedirs(MODELS_DIR, exist_ok=True)
    print(f"Creating models directory at: {MODELS_DIR}\n")

    for filename, url in MODELS.items():
        dest_path = os.path.join(MODELS_DIR, filename)
        if os.path.exists(dest_path):
            print(f"[EXISTS] {filename} already exists at {dest_path}. Skipping.")
            continue

        print(f"[DOWNLOADING] {filename} from {url}")
        try:
            urllib.request.urlretrieve(url, dest_path, report_progress)
            print(f"\n[SUCCESS] Saved {filename} to {dest_path}\n")
        except Exception as e:
            print(f"\n[ERROR] Failed to download {filename}: {e}\n")

if __name__ == "__main__":
    main()
