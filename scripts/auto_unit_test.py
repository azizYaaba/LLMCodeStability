import os
import subprocess
from pathlib import Path

UNITTEST_SUFFIX = "unittest"
UNITTEST_SCRIPT = "unit_test.py"

def find_generated_files(root_dir):
    return list(Path(root_dir).rglob("generated_completions_*.jsonl"))

def build_output_path(generated_file: Path):
    folder = generated_file.parent
    name = generated_file.name.replace("generated_completions_", f"{UNITTEST_SUFFIX}_")
    return folder / name

def main(ROOT_DIR):
    generated_files = find_generated_files(ROOT_DIR)

    for gen_path in generated_files:
        output_path = build_output_path(gen_path)
        print(f"🧪 Running unit tests for {gen_path} → {output_path}")

        subprocess.run([
            "python", UNITTEST_SCRIPT,
            "--path_to_file", str(gen_path),
            "--output_file", str(output_path)
        ], check=True)

    print("\n✅ All unit tests completed.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root_dir", required=True, help="Directory containing generated files.")
    args = parser.parse_args()
    main(args.root_dir)