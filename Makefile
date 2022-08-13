SHELL:=/bin/bash

WORKDIR_PATH=/depthai
REPO_PATH:=$(dir $(abspath $(firstword $(MAKEFILE_LIST))))
IMAGE_TAG?=pvphan/depthai:0.1
IP_ADDR=$(shell ./getlocalip.sh)


RUN_FLAGS = \
	--rm \
	-it \
	--network=host \
	-e DISPLAY=${IP_ADDR}:0 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
	--volume=${REPO_PATH}:${WORKDIR_PATH} \
		${IMAGE_TAG}

shell: image
	docker run ${RUN_FLAGS} bash

image:
	docker build -t ${IMAGE_TAG} .

