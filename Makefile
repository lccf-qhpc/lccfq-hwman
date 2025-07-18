PROTO_SRC_DIR := ./hwman/grpc/protobufs
PROTO_OUT_DIR := ./hwman/grpc/protobufs_compiled
PROTO_FILES := $(shell find $(PROTO_SRC_DIR) -name '*.proto')

# Detect OS and set sed options accordingly
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
    SED_INPLACE := sed -i ''
else
    SED_INPLACE := sed -i
endif

.PHONY: all protos clean

all: protos

protos:
	@mkdir -p $(PROTO_OUT_DIR)
	touch $(PROTO_OUT_DIR)/__init__.py
	uv run -m grpc_tools.protoc \
	  -I. \
	  --python_out=$(PROTO_OUT_DIR) \
	  --grpc_python_out=$(PROTO_OUT_DIR) \
	  $(PROTO_FILES)
	@find $(PROTO_OUT_DIR) -type f -name "*.py" -exec mv {} $(PROTO_OUT_DIR) \;
	@find $(PROTO_OUT_DIR) -type d -not -path "$(PROTO_OUT_DIR)" -exec rm -rf {} +
	@$(SED_INPLACE) 's/from hwman.grpc.protobufs import/from hwman.grpc.protobufs_compiled import/g' $(PROTO_OUT_DIR)/*.py

clean:
	rm -rf $(PROTO_OUT_DIR)/* 