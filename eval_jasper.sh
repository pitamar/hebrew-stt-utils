#!/bin/bash
set -e

# export KALDI_ROOT=/tmp
# 
# LM_PATH=/code/hebrew-stt/lm/wiki.bin
# 
# python3 ../nemo/examples/asr/jasper_eval.py \
# 	--model_config /code/hebrew-stt/jasper_checkpoints/quartznet_orig/quartznet15x5_custom.yaml \
# 	--load_dir /code/hebrew-stt/jasper_checkpoints/quartznet_multi_gpu_41_WER/ \
# 	--eval_datasets $PWD/manifest/normalized/jasper_manifest.val.json \
#         --batch_size 32 \
#         --amp_opt_level O1 \
#         --lm_path $LM_PATH \
# 	--alpha 0.99 \
#         --beta 0.6 \
#         --beam_width 128 \
#         ;


export KALDI_ROOT=/tmp

#LM_PATH="/code/hebrew-stt/lm/wiki.bin"
LM_PATH="/code/corpus/combined.wiki.opensubtitles.bin"

python3 ../nemo/examples/asr/other/jasper_eval.py \
	--model_config /code/hebrew-stt/jasper_checkpoints/quartznet_orig/quartznet15x5_custom.yaml \
	--load_dir jasper_checkpoints/quartznet_multi_gpu_31.84_WER \
	--eval_datasets $PWD/manifest/normalized/jasper_manifest.test.json \
        --batch_size 32 \
        --amp_opt_level O0 \
        --lm_path "$LM_PATH" \
	--alpha 0.7 \
	--alpha_max 0.82 \
	--alpha_step 0.02 \
	--beta 0.66 \
	--beta_max 0.8 \
	--beta_step 0.02 \
        ;
        #--alpha 0.76 \
        #--beta 0.72 \
	#;
