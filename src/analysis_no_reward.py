import argparse
import glob
import io
import multiprocessing as mp
import os
import re
import sqlite3
import sys
from contextlib import redirect_stderr, suppress

import pandas as pd
import tqdm.autonotebook as tqdm
from func_timeout import FunctionTimedOut, func_timeout
from tabulate import tabulate

from utils import read_jsonl_file, read_tsv_file, write_jsonl_file


def execute_sql(datum):
    conn = sqlite3.connect(datum["db_path"])
    cursor = conn.cursor()
    cursor.execute(datum["predicted_sql"])
    predicted_res = set(cursor.fetchall())
    cursor.execute(datum["SQL"])
    ground_truth_res = set(cursor.fetchall())
    if len(predicted_res) == 0:
        return "pass: incorrect-empty"
    elif predicted_res == ground_truth_res:
        return "pass: correct"
    else:
        return "pass: incorrect"


def execute_sql_robust(args, datum, i):
    stderr = io.StringIO()
    with suppress(RuntimeError, ReferenceError), redirect_stderr(stderr):
        try:
            evaluation = func_timeout(
                args.meta_time_out, execute_sql, args=(datum,)
            )
        except KeyboardInterrupt:
            sys.exit(0)
        except FunctionTimedOut:
            evaluation = "error: timeout"
        except Exception as e:
            evaluation = "error: <error>"
    return (i, evaluation)


def evaluate(args, data):
    exec_results = []

    def result_callback(result):
        exec_results.append(result)
        pbar.update(1)

    pbar = tqdm.tqdm(total=len(data), desc="Processing", unit="item")
    if args.num_cpus > 1:
        pool = mp.Pool(processes=args.num_cpus)
        for i, datum in enumerate(data):
            evaluation = datum.get("evaluation", "")
            if evaluation is None or len(evaluation) == 0 or evaluation == "pass: ??":
                pool.apply_async(execute_sql_robust, args=(args, datum, i), callback=result_callback)
            else:
                pbar.update(1)
        pool.close()
        pool.join()
    else:    
        for i, datum in enumerate(data):
            evaluation = datum.get("evaluation", "")
            if len(evaluation) == 0 or evaluation == "pass: ??":
                result = execute_sql_robust(args, datum, i)
                result_callback(result)
            else:
                pbar.update(1)
    pbar.close()

    for i, evaluation in exec_results:
        data[i]["evaluation"] = evaluation

    data_eval = pd.DataFrame.from_records(
        [
            {
                "difficulty": datum["difficulty"],
                "evaluation": datum["evaluation"],
                "db_id": datum["db_id"],
            }
            for datum in data
        ]
    )
    data_eval["if_correct"] = data_eval["evaluation"] == "pass: correct"
    print("Overall Accuracy: ", data_eval["if_correct"].mean())

    evaluation_counts = data_eval.groupby("evaluation").size().reset_index(name="count")
    evaluation_counts.sort_values("count", ascending=False, inplace=True)
    print("Evaluation Counts:")
    print(tabulate(evaluation_counts, headers="keys", tablefmt="pipe"))

    results = (
        data_eval.groupby(["db_id"])
        .agg(
            correct=("if_correct", "sum"),
            total=("if_correct", "count"),
        )
        .reset_index()
    )
    results["accuracy"] = results["correct"] / results["total"]
    results.sort_values("db_id", ascending=False, inplace=True)
    print(tabulate(results, headers="keys", tablefmt="pipe"))
    results = (
        data_eval.groupby(["difficulty"])
        .agg(
            correct=("if_correct", "sum"),
            total=("if_correct", "count"),
        )
        .reset_index()
    )
    results["accuracy"] = results["correct"] / results["total"]
    results.sort_values("difficulty", ascending=False, inplace=True)
    print(tabulate(results, headers="keys", tablefmt="pipe"))
    return data


def select(data):
    for datum in data:
        best_sql, best_score = "dummy", float("-inf")
        for sql in datum["responses"]:
            logprob = max(datum["responses"][sql]["all_logprobs"])
            score =  logprob
            if score > best_score:
                best_score = score
                best_sql = sql
        datum["predicted_sql"] = best_sql


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_file", type=str, required=True)
    parser.add_argument("--gt_sql_file", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--num_cpus", type=int, default=1, help="Number of CPUs to use for evaluation")
    parser.add_argument("--meta_time_out", type=float, default=30.0, help="Timeout for evaluation")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    data = read_jsonl_file(args.results_file)

    gt_sql_data = read_tsv_file(args.gt_sql_file)
    for datum in data:
        datum["gt_sql"] = gt_sql_data[datum['question_id']][0]

    print("Selecting")
    select(data)
    print("Evaluating")
    evaluate(args, data)


if __name__ == "__main__":
    main()
