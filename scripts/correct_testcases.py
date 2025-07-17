import pandas as pd
from pathlib import Path
from tqdm import tqdm  

def transform_tests(tests: dict) -> list:
    """Convert separate input/output lists into a list of {'input': ..., 'output': ...} dicts."""
    inputs = tests.get("input", [])
    outputs = tests.get("output", [])
    return [{"input": inp.strip(), "output": out.strip()} for inp, out in zip(inputs, outputs)]

def correct_testcases(original_file: str, completion_file: str):
    """Overwrite completion_file with corrected public/private test format using original_file as reference."""
    df_source = pd.read_json(original_file, lines=True)
    df_target = pd.read_json(completion_file, lines=True)

    # Map problem_id → test cases
    source_map = {
        row["problem_id"]: {
            "public_tests": row.get("public_tests", {}),
            "private_tests": row.get("private_tests", {})
        }
        for _, row in df_source.iterrows()
    }

    corrected = []
    for _, row in tqdm(df_target.iterrows(), total=len(df_target), desc=f"Correcting {Path(completion_file).name}"):
        pid = row.get("problem_id")
        if pid in source_map:
            if isinstance(source_map[pid].get("public_tests"), dict):
                row["public_tests"] = transform_tests(source_map[pid]["public_tests"])
            if isinstance(source_map[pid].get("private_tests"), dict):
                row["private_tests"] = transform_tests(source_map[pid]["private_tests"])
        corrected.append(row)

    pd.DataFrame(corrected).to_json(completion_file, orient="records", lines=True, force_ascii=False)

def find_generated_files(root_dir: str):
    return list(Path(root_dir).rglob("generated_completions_*.jsonl"))

def main(root_dir: str, original_file: str):
    generated_files = find_generated_files(root_dir)
    if not generated_files:
        print("❌ No generated_completions_*.jsonl files found.")
        return

    print(f"🔍 Found {len(generated_files)} generated files.")
    for gen_path in tqdm(generated_files, desc="Processing files"):
        correct_testcases(original_file, str(gen_path))

    print("\n✅ All files corrected.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root_dir", required=True, help="Directory containing generated files.")
    parser.add_argument("--original_file", required=True, help="Path to the original dataset (with ground truth testcases).")

    args = parser.parse_args()
    main(args.root_dir, args.original_file)