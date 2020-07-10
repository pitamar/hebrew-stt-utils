#!/bin/bash

set -e

export WORKDIR=$PWD/workdir/quartznet_multi_gpu
export CUDA_VISIBLE_DEVICES=0,1

echo workdir: $WORKDIR
mkdir -p $WORKDIR/logs

python -m torch.distributed.launch \
	--nproc_per_node 2 \
	../nemo/examples/asr/other/quartznet.py \
	--model_config $PWD/jasper_checkpoints/quartznet_orig/quartznet15x5_custom.yaml \
	--checkpoint_dir $WORKDIR/model_checkpoints \
	--load_dir $PWD/jasper_checkpoints/quartznet_initial/ \
	--work_dir $WORKDIR \
	--train_dataset $PWD/manifest/normalized/jasper_manifest.train.json \
	--eval_datasets $PWD/manifest/normalized/jasper_manifest.val.json \
	--tensorboard_dir $WORKDIR/tensorboard \
	--batch_size 8 \
	--num_epochs 30 \
	--lr 0.0005 \
	--warmup_steps 0000 \
	--weight_decay 0.0001 \
	--amp_opt_level O0 \
	2>&1 | tee $WORKDIR/logs/quartznet_multi_gpu.log;

