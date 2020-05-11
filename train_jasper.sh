#!/bin/bash

set -e

export WORKDIR=$PWD/workdir/jasper
export CUDA_VISIBLE_DEVICES=1

echo workdir: $WORKDIR
mkdir -p $WORKDIR/logs

python ../nemo/examples/asr/jasper.py \
--model_config $PWD/jasper_checkpoints/jasper_orig/jasper10x5dr_custom.yaml \
--checkpoint_dir $WORKDIR/model_checkpoints \
--load_dir $PWD/jasper_checkpoints/jasper_orig \
--work_dir $WORKDIR \
--train_dataset $PWD/manifest/normalized/jasper_manifest.train.json \
--eval_datasets $PWD/manifest/normalized/jasper_manifest.val.json \
--tensorboard_dir $WORKDIR/tensorboard \
--batch_size 8 \
--num_epochs 100 \
--lr 0.015 \
--warmup_steps 8000 \
--weight_decay 0.00 \
--amp_opt_level O0 \
2>&1  | tee $WORKDIR/logs/jasper.log;
