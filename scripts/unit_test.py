from fire import Fire
import json
import os
import uuid
from tqdm import tqdm
import traceback
import multiprocessing
import sys

def load_jsonl(path):
    items = []
    with open(path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"⚠️ Skipping line {line_num}: JSON decode error - {e}")
    return items

def _worker(code, conn):
    import io, sys, traceback, unittest

    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()

    try:
        globs = {}
        exec(code, globs)

        suite = unittest.TestLoader().loadTestsFromTestCase(globs["TestDataclass"])
        runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
        result = runner.run(suite)

        if result.wasSuccessful():
            conn.send({"category": "success", "stdout": sys.stdout.getvalue()})
        else:
            conn.send({
                "category": "test_failure",
                "stdout": sys.stdout.getvalue(),
                "error": sys.stderr.getvalue() or "Test failed"
            })
    except Exception:
        conn.send({
            "category": "execution_error",
            "error": traceback.format_exc()
        })
    finally:
        conn.close()  

def run_unittest(problem, timeout=10):
    generated_solution = problem.get("generated_solution", "")

    public_tests = problem.get("public_tests", [])
    private_tests = problem.get("private_tests", [])
    problem_id = problem.get("problem_id")
    solution_id = problem.get("solution_id", str(uuid.uuid4()))

    complexity = problem.get("complexity")
    solution_code = problem.get("solution_code")
    dataclass_code = problem.get("dataclass_code")

    if not generated_solution.strip():
        return {
            "problem_id": problem_id,
            "solution_id": solution_id,
            "generated_solution":generated_solution,
            "public_tests": public_tests,
            "private_tests": private_tests,
            "solution_code":solution_code,
            "dataclass_code":dataclass_code,
            "complexity":complexity,
            "category": "empty_code_extracted",
            "error": "No code provided in 'generated_solution'.",
            "raw_llm_output": problem.get("raw_llm_output", ""),
        }

    # Construct dynamic unittest class based on public_tests
    test_methods = []
    for i, case in enumerate(public_tests):
        input_str = json.dumps(case.get("input", ""))
        expected_output = json.dumps(case.get("output", ""))

        test_method = f"""
            def test_case_{i}(self):
                input_str = {input_str}
                expected = {expected_output}
                input_lines = input_str.strip().split("\\n")
                result = solve(input_lines)
                self.assertEqual(str(result).strip(), expected.strip(), f"Output mismatch: {{result}} != {{expected}}")
        """
        test_methods.append(test_method)

    test_code = f"""
import unittest

class TestDataclass(unittest.TestCase):\n{''.join(test_methods)}
"""

    full_code = generated_solution + "\n\n" + test_code

    parent_conn, child_conn = multiprocessing.Pipe()
    p = multiprocessing.Process(target=_worker, args=(full_code, child_conn))
    p.start()
    p.join(timeout)

    result = {
        "problem_id": problem_id,
        "solution_id": solution_id,
        "generated_solution": generated_solution,
        "num_tests": len(public_tests),
        "public_tests": public_tests,
        "private_tests": private_tests,
        "solution_code":solution_code,
        "dataclass_code":dataclass_code,
        "complexity":complexity,
        
    }

    if p.is_alive():
        p.terminate()
        p.join()
        result.update({
            "category": "timeout",
            "error": f"Execution timed out after {timeout} seconds"
        })
    elif parent_conn.poll():
        result.update(parent_conn.recv())
    else:
        result.update({
            "category": "no_response",
            "error": "No response received from subprocess"
        })

    return result

def main(path_to_file: str, output_file: str = "unit_test_results.jsonl"):
    problems = load_jsonl(path_to_file)
    print(f"✅ Loaded {len(problems)} problems from {path_to_file}")

    with open(output_file, "w", encoding="utf-8") as out_f:
        for problem in tqdm(problems, desc="🔍 Running unit tests"):
            result = run_unittest(problem)
            out_f.write(json.dumps(result, ensure_ascii=False) + "\n")

    print(f"\n✅ All test results saved to {output_file}")

if __name__ == "__main__":
    Fire(main)