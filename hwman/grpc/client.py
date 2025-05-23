

import logging

import grpc
from protobufs_compiled import messages_pb2, messages_pb2_grpc


def run():
    print("Starting gRPC client")
    with grpc.insecure_channel("localhost:50051") as channel:
        stub = messages_pb2_grpc.JobDispatchStub(channel)
        response = stub.SubmitJob(messages_pb2.JobRequest(id=1, type="dummy"))
        print(f"Response received: {response.id}, type: {response.type}, result: {response.result}")

if __name__ == "__main__":
    logging.basicConfig()
    run()