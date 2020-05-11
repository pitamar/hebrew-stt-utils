#!/bin/bash

set -e

export WORKDIR=$PWD/workdir/quartznet
export CUDA_VISIBLE_DEVICES=0

echo workdir: $WORKDIR
mkdir -p $WORKDIR/logs

python ../nemo/examples/asr/quartznet.py \
--model_config $PWD/jasper_checkpoints/quartznet_orig/quartznet15x5_custom.yaml \
--checkpoint_dir $WORKDIR/model_checkpoints \
--load_dir $PWD/jasper_checkpoints/quartznet_orig/ \
--work_dir $WORKDIR \
--train_dataset $PWD/manifest/normalized/jasper_manifest.train.json \
--eval_datasets $PWD/manifest/normalized/jasper_manifest.val.json \
--tensorboard_dir $WORKDIR/tensorboard \
--batch_size 16 \
--num_epochs 100 \
--lr 0.015 \
--warmup_steps 8000 \
--weight_decay 0 \
2>&1 | tee $WORKDIR/logs/quartznet.log;
