# LLMCodeStability

This project evaluates the **stability of generated code** by Large Language Models (LLMs). It operates in multiple stages (e.g., code generation, unit testing), which are described below and extended further later.

---

## 🧠 1. Code Generation

Generates code solutions for programming problems using various LLMs (e.g., OpenAI, DeepSeek, Claude, etc.). The pipeline supports:

- Multiple **models**
- Variable **temperature settings**
- Generation in **parallel** for scalability
- Option to include or strip **examples** (input/output specs)
- JSONL output storing completions with metadata

### Input Format

Each input file must be a `.jsonl` file with entries like:

```json
{
  "problem_id": "merge_sorted_lists",
  "description": "Write a function to merge two sorted lists..."
}
```

### Output

Each completion is saved with fields like:

- `problem_id`
- `solution_id`
- `generated_solution`
- `model`, `temperature`, etc.

---

## ✅ 2. Unit Testing

Once solutions are generated, they are tested using unit tests to evaluate:

- **Functional correctness**: does the code solve the problem?
- **Execution safety**: runs in an isolated subprocess to avoid crashes
- **Stability**: checks robustness across different generations

### How it Works

- Each generated solution is tested with a dynamically constructed `unittest.TestCase` based on the problem's `public_tests`.
- The code and tests are executed in a separate process with timeout control.
- Results are collected including:
  - Pass/fail status
  - Error messages or exceptions
  - Timeout or crash information

### Input Format

Each `.jsonl` file should contain:
```json
{
  "problem_id": "sum_numbers",
  "generated_solution": "def solve(lines): return sum(map(int, lines))",
  "public_tests": [{"input": "1\n2", "output": "3"}]
}
```

### Output

Each entry includes:
- Pass/fail status for each test
- Optional traceback or exception
- Test summary for reporting and aggregation

---

## 📁 Folder Structure

```
.
├── data/                   # Input problem descriptions
├── results/                # Generated code and test logs
├── scripts/
│   ├── codegenerate_parallel-BigOBench.py
│   └── unit_test_runner.py
├── README.md
```

---

## 🔧 Getting Started

Install dependencies:

```bash
pip install -r requirements.txt
```

Run code generation:

```bash
python scripts/codegenerate_parallel-BigOBench.py --input_file=... --models=... --temperatures=...
```

Run unit tests:

```bash
python scripts/unit_test_runner.py --input_file=... --output_dir=...
```

---

## 📈 Metrics

The project supports evaluation of:

- 
