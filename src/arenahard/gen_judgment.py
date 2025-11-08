import json
import yaml
import argparse
import os
import concurrent.futures

from tqdm import tqdm

from arenahard.utils.completion import (
    load_questions,
    registered_api_completion,
    load_questions,
    load_model_answers,
    get_endpoint,
    make_config,
)

from arenahard.utils.judge_utils import JUDGE_SETTINGS


def get_score(judgment, patterns):
    import re
    for pattern in patterns:
        pattern = re.compile(pattern)
        
        matches = pattern.findall(judgment.upper())
        matches = [m for m in matches if m != ""]
        
        if len(set(matches)) > 0:
            return matches[-1].strip("\n")
    return None


def pairwise_judgment(question, baseline, answer, reference, configs, settings):
    prompt_args = {
        "QUESTION": question['prompt'],
        "ANSWER_A": baseline["messages"][-1]["content"]['answer'],
        "ANSWER_B": answer["messages"][-1]["content"]['answer'],
    }
    
    if reference:
        prompt_args[f"REFERENCE"] = reference["messages"][-1]["content"]['answer']
        
    user_prompt = configs["prompt_template"].format(**prompt_args)
    messages = [
        {
            "role": "system", 
            "content": JUDGE_SETTINGS[question["category"]]["system_prompt"],
        },
        {
            "role": "user", 
            "content": user_prompt,
        }
    ]

    # build arguments for api completions
    kwargs = settings | {
        "api_dict": get_endpoint(settings["endpoints"]),
        "messages": messages,
    }
    #kwargs['temperature'] = 0.1
    kwargs['temperature'] = configs['temperature']
    kwargs['max_tokens'] = configs['max_tokens']
    kwargs['reasoning_effort'] = configs['reasoning_effort']
    
    api_completion_func = registered_api_completion[settings["api_type"]]
    output = api_completion_func(**kwargs)
    
    if output is None:
        return None

    #print(output['answer'])
    #print(configs["regex_patterns"])
    score = get_score(output['answer'], configs["regex_patterns"])

    result = {
        "score": score,
        "judgment": output,
        "prompt": messages,
    }
    return result


def judgment(args):
    answer = args['answer']
    baseline = args['baseline']
    
    output = {
        "uid": args['question']["uid"],
        "category": args['question']["category"],
        "judge": args['configs']['judge_model'],
        "model": answer["model"],
        "baseline": baseline["model"],
        "games": []
    }

    # map label to score
    label_to_score = [
        "A>B",
        "A>>B",
        "A=B",
        "A<<B",
        "A<B",
        "B>A",
        "B>>A",
        "B=A",
        "B<<A",
        "B<A"
    ]

    num_of_retries = 10
    for idx in range(num_of_retries):
        # round 1
        result = pairwise_judgment(
            question=args['question'],
            baseline=baseline,
            answer=answer,
            reference=args['reference'],
            configs=args['configs'],
            settings=args['settings'],
        )
        #if result["score"] != None and result["score"] in label_to_score.keys()):
        if result["score"] in label_to_score:
            break
        elif result["score"] == None:
            uid = output["uid"]
            print(f"Rerun experiment for {uid}")

    output["games"].append(result)
        
    for idx in range(num_of_retries):
        # round 2
        result = pairwise_judgment(
            question=args['question'],
            baseline=answer,
            answer=baseline,
            reference=args['reference'],
            configs=args['configs'],
            settings=args['settings'],
        )
        if result["score"] in label_to_score:
            break
        elif result["score"] == None:
            uid = output["uid"]
            print(f"Rerun experiment for {uid}")

    output["games"].append(result)

    with open(args['output_file'], "a", encoding="utf-8") as f:
        f.write(json.dumps(output, ensure_ascii=False) + "\n")



def run (setting_file, endpoint_file, config_path, question_path, answer_path):

    configs = make_config(os.path.join(config_path, setting_file))
    endpoint_list = make_config(os.path.join(config_path, endpoint_file))

    print(f'judge model: {configs["judge_model"]}, reference: {configs["reference"]}, temperature: {configs["temperature"]}, max tokens: {configs["max_tokens"]}, reasoning effort: {configs["reasoning_effort"]},')

    question_file = os.path.join(question_path, configs["bench_name"], "question.jsonl")
    answer_dir = os.path.join(answer_path, configs["bench_name"], "model_answer")
    
    print(f"Question file: {question_file}")
    print(f"Answer dir: {answer_dir}")
    

    questions = load_questions(question_file)
    model_answers = load_model_answers(answer_dir)
    
    # if user choose a set of models, only judge those models
    models = [model for model in configs["model_list"]]
    print(f"The models to judge are: {models}")
        
    if configs["reference"]:
        assert not configs["reference"] in models, "ERROR: one of the models being evaluated is used as reference."
        ref_answers = [answer_dir[model] for model in configs["reference"]]
    else:
        ref_answers = None
    
    output_files = {}
    output_dir = f"{answer_path}/{configs['bench_name']}/model_judgment/{configs['judge_model']}"
    for model in models:
        output_files[model] = os.path.join(
            output_dir,
            f"{model}.jsonl",
        )

    for output_file in output_files.values():
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

    existing_judgments = load_model_answers(output_dir)

    endpoint_settings = endpoint_list[configs["judge_model"]]

    with concurrent.futures.ThreadPoolExecutor(max_workers=endpoint_settings["parallel"]) as executor:
        futures = []
        for model in models:
            count = 0
            for question in questions:
                uid = question["uid"]

                kwargs = {}
                kwargs["question"] = question
                if model in model_answers and not uid in model_answers[model]:
                    print(f"Warning: {model} answer to {question['uid']} cannot be found.")
                    continue

                if model in existing_judgments and uid in existing_judgments[model]:
                    count += 1
                    continue

                kwargs["answer"] = model_answers[model][uid]
                kwargs["baseline"] = model_answers[
                    JUDGE_SETTINGS[question["category"]]["baseline"]
                ][uid]
                
                if ref_answers:
                    kwargs["reference"] = [ref_answer[uid] for ref_answer in ref_answers]
                else:
                    kwargs["reference"] = None
                    
                kwargs["configs"] = configs
                kwargs["settings"] = endpoint_settings
                kwargs["output_file"] = output_files[model]
                                
                future = executor.submit(judgment, kwargs)
                futures.append(future)

            if count > 0:
                print(f"{count} number of existing judgments")

        for future in tqdm(
            concurrent.futures.as_completed(futures), total=len(futures)
        ):
            future.result()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--setting-file", type=str, default=os.path.join("config", "arena-hard-v2.0.yaml")
    )
    parser.add_argument(
        "--endpoint-file", type=str, default=os.path.join("config", "api_config.yaml")
    )
    parser.add_argument(
        "--config-path", type=str, default=os.path.join(".", "src", "arenahard" )
    )
    parser.add_argument(
        "--question-path", type=str, default=os.path.join(".", "src", "arenahard", "data")
    )
    parser.add_argument(
        "--answer-path", type=str, default=os.path.join(".", "src", "arenahard", "data")
    )
    args = parser.parse_args()
    print(args)
    run( setting_file = args.setting_file, endpoint_file = args.endpoint_file, config_path = args.config_path, question_path = args.question_path, answer_path = args.answer_path)

