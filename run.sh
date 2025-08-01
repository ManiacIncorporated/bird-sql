model_output_dir=output/generations/
test_input_file=data/test_all.jsonl
sql_output_dir=output/with_results/
sql_output_file=output/with_results/data_with_results.jsonl
gt_sql_file=data/test_gold_sqls.txt
analysis_output_dir=output/analysis/

num_gpus=1
num_prompts_per_query=1
num_samples_per_prompt=1
num_shots=1
sql_timeout=40.0
num_cpus=10


python src/generate.py --input_file $test_input_file --output_dir $model_output_dir --num_gpus $num_gpus --num_prompts_per_query $num_prompts_per_query --num_samples_per_prompt $num_samples_per_prompt --num_shots $num_shots
python src/process_sqls.py --input_file $test_input_file --generations_dir $model_output_dir --output_dir $sql_output_dir --compare_against_gt --sql_timeout $sql_timeout --num_prompts_per_query $num_prompts_per_query
python src/analysis_no_reward.py --results_file $sql_output_file --gt_sql_file $gt_sql_file --output_dir $analysis_output_dir --num_cpus $num_cpus

# python src/generate.py --input_file data/test_all.jsonl --output_dir output/generations/ --num_gpus 1 --num_prompts_per_query 1 --num_samples_per_prompt 1 --num_shots 1
# python src/process_sqls.py --input_file data/test_all.jsonl --generations_dir output/generations/ --output_dir output/with_results/ --compare_against_gt --sql_timeout 40.0 --num_prompts_per_query 1
# python src/analysis_no_reward.py --results_file output/with_results/data_with_results.jsonl --gt_sql_file data/test_gold_sqls.txt --output_dir output/analysis --num_cpus 10