from fire import Fire
from openai import OpenAI
import json
import os
import uuid
from tqdm import tqdm
import re
import sys
from typing import List, Optional
import concurrent.futures
import threading
import argparse
import ollama


def load_dataset(path):
    """
    Load problems from a JSONL file at the given path.
    Ensures that all problems have unique `problem_id`s.
    """
    problems = []
    seen_ids = set()

    with open(path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f):
            line = line.strip()
            if not line:
                continue

            problem = json.loads(line)
            pid = problem.get("problem_id")

            if not pid:
                raise ValueError(f"Missing 'problem_id' at line {line_num}")

            if pid in seen_ids:
                continue

            seen_ids.add(pid)
            problems.append(problem)

    return problems

def strip_examples(description: str) -> str:
    """
    Removes the examples and input/output sections from a problem description string.
    """
    # Pattern matches any of the following as start of example section
    patterns = [
        r"\n*Examples?\n*",
        r"\n*Sample\s+(Input|Output)\n*",
        r"\n*Input\n*",
        r"\n*Output\n*"
    ]

    for pattern in patterns:
        match = re.search(pattern, description, flags=re.IGNORECASE)
        if match:
            return description[:match.start()].strip()

    return description.strip()  # fallback: return original if no match


import ollama


def create_completion(client, model, messages, temperature=0):
    """
    Supports Ollama (Python client), OpenRouter, and vLLM (OpenAI-compatible client).
    """
    # --- If using Ollama's Python client ---
    if isinstance(client, ollama.Client):
        try:
            response = client.chat(
                model=model,
                messages=messages,
                options={"temperature": temperature}
            )
            return response['message']['content'].strip()
        except Exception as e:
            print(f"❌ Ollama Python client error: {e}")
            return ""

    # --- OpenRouter / vLLM via OpenAI-compatible SDK ---
    else:
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=2048,
                temperature=temperature,
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ OpenAI-compatible client error: {e}")
            return ""

def extract_code_block(content):
    """
    Extracts a Python code block from the LLM-generated content.
    """
    match = re.search(
        r"```(?:python|py)?\s*\n(.*?)\n\s*```",
        content,
        re.DOTALL | re.IGNORECASE
    )
    if match:
        return match.group(1).strip()

    lines = content.splitlines()
    code_lines = []
    inside_code = False

    for line in lines:
        if line.strip().startswith("def solve"):
            inside_code = True
        if inside_code:
            code_lines.append(line)

    return "\n".join(code_lines).strip() if code_lines else ""




lock = threading.Lock()  # For safe file writes

def main(
    base_url: str,
    path_to_data_file: str,
    output_prefix: str = "generated_completions",
    completions_per_problem: int = 5,
    platform: str = "openrouter",
    withoutexemples: bool = False,
    *models: str,
    temperatures: str = "0,0.7,0.95",
    max_problems: Optional[int] = None,
    num_threads: int = 65
):
    if platform.lower() == "ollama":
        client = ollama.Client(host=base_url)
    
    elif platform.lower() == "vllm":
        client = OpenAI(base_url=base_url, api_key="EMPTY")
    
    elif platform.lower() == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("Environment variable 'OPENROUTER_API_KEY' not found.")
        client = OpenAI(base_url=base_url, api_key=api_key)
    
    else:
        raise ValueError(f"Unsupported platform: {platform}")
    problems = load_dataset(path_to_data_file)
    if max_problems is not None:
        problems = problems[:int(max_problems)]
    print(f"Starting generation for {len(problems)} problems with {completions_per_problem} completions each.")

    temperature_list = [float(t.strip()) for t in temperatures.split(",")]

    for model in models:
        for temperature in temperature_list:
            print(f"\n🚀 Using model: {model} with temperature: {temperature}")
            subdir = "withoutexamples" if withoutexemples else "withexamples"
            output_file = f"results/code_contests/{subdir}/{model.replace('/', '_')}/{output_prefix}_{model.replace('/', '_')}_temp{temperature}.jsonl"
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            completed_problem_keys = set()
            if os.path.exists(output_file):
                print(f"Output file {output_file} exists. Resuming...")
                with open(output_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            key = (data["problem_id"], data.get("completion_index", 0))
                            completed_problem_keys.add(key)
                        except Exception:
                            continue
                print(f"Found {len(completed_problem_keys)} completed completions.")

            def process_one_completion(problem, i):
                problem_id = problem.get("problem_id")
                key = (problem_id, i)
                problem_description = (
                    strip_examples(problem.get('description', ''))
                    if withoutexemples
                    else problem.get('description', '')
                )
                if key in completed_problem_keys:
                    return
                try:
                    messages = [
                        {
                            "role": "system",
                            "content": (
                                "You are a highly skilled competitive programmer. Your task is to write ONLY the complete Python code for a function named `solve`.\n\n"
                                "### Function Requirements:\n"
                                "- The function signature must be: `def solve(input_lines: list[str]) -> str`\n"
                                "- It will receive input as a list of strings (`input_lines`).\n"
                                "- Return the final output as a string (not using print).\n"
                                "- Match the exact expected format.\n\n"
                                "### Code Block Format:\n"
                                "- Return your solution enclosed in triple backticks like:\n```python\n<your_code_here>\n```"
                            )
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Here is the problem statement:\n\n"
                                f"{strip_examples(problem.get('description', '')).strip()}\n\n"
                                f"Write the correct implementation of `solve` based on this description."
                            )
                        } 
                    ]
                    raw_llm_output = create_completion(client, model, messages, temperature)
                    generated_solution_code = extract_code_block(raw_llm_output)
                    solution_id = str(uuid.uuid4())

                    info = {
                        "problem_id": problem_id,
                        "solution_id": solution_id,
                        "completion_index": i,
                        "description": problem_description,
                        "generated_solution": generated_solution_code,
                        "difficulty": problem.get("difficulty"),
                        "solutions": problem.get("solutions"),
                        "generated_tests": problem.get("generated_tests"),
                        "public_tests": problem.get("tests", {}).get("public_tests", []),
                        "private_tests": problem.get("tests", {}).get("private_tests", []),
                        "raw_llm_output": raw_llm_output
                    }
                except Exception as e:
                    info = {
                        "problem_id": problem_id,
                        "solution_id": str(uuid.uuid4()),
                        "completion_index": i,
                        "description": problem_description,
                        "error_category": "api_call_failure",
                        "error_message": str(e),
                        "generated_solution": locals().get("generated_solution_code", ""),
                        "raw_llm_output": locals().get("raw_llm_output", ""),
                        "difficulty": problem.get("difficulty"),
                        "solutions": problem.get("solutions"),
                        "generated_tests": problem.get("generated_tests"),
                        "public_tests": problem.get("tests", {}).get("public_tests", []),
                        "private_tests": problem.get("tests", {}).get("private_tests", [])
                    }

                with lock:
                    with open(output_file, "a", encoding="utf-8") as f:
                        f.write(json.dumps(info, ensure_ascii=False) + "\n")

            jobs = [
                (problem, i)
                for problem in problems
                for i in range(completions_per_problem)
                if (problem.get("problem_id"), i) not in completed_problem_keys
            ]

            print(f"Launching {len(jobs)} jobs across {num_threads} threads...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
                list(tqdm(executor.map(lambda args: process_one_completion(*args), jobs), total=len(jobs), desc="Generating completions"))

            print(f"\n✅ Finished processing. Output saved to: {output_file}")

    print("\n🎉 All model/temperature combinations processed.")


if __name__ == "__main__": 
    Fire(main)