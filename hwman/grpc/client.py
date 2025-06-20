import logging

import grpc
from protobufs_compiled import jobs_pb2, jobs_pb2_grpc  # type: ignore


def run():
    print("Starting gRPC client")
    with grpc.insecure_channel("localhost:50051") as channel:
        stub = jobs_pb2_grpc.JobDispatchStub(channel)
        job = jobs_pb2.Job(type=jobs_pb2.JobType.JOB_TYPE_DUMMY)
        response = stub.SubmitJob(job)
        print(
            f"Response received: {response.id}, type: {response.type}, result: {response.result}"
        )


if __name__ == "__main__":
    logging.basicConfig()
    run()
