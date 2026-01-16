
## Terminal 1 
```
vllm serve Qwen/Qwen2.5-1.5B-Instruct
```

## Terminal 2 in virtual env
```
git clone https://github.com/neuralmagic/arena-hard-auto.git
cd arena-hard
pip3 install -r requirements.txt
```

Generate Answer
```
python3 src/arenahard/gen_answer.py  --config-file custom_gen_answer_config.yaml --endpoint-file custom_api_config.yaml --question-path ./exampleconfig --config-path ./exampleconfig
```

Generate Judgement
```
python3 src/arenahard/gen_judgment.py  --setting-file arena-hard-v2.0.yaml --endpoint-file custom_api_config.yaml --config-path ./exampleconfig
```
