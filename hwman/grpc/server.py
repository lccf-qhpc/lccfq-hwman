import logging

import grpc
from concurrent import futures

from protobufs_compiled import messages_pb2, messages_pb2_grpc



class JobDispatchServicer(messages_pb2_grpc.JobDispatchServicer):

    def SubmitJob(self, request, context):
        # Process the job request and return a response
        print(f"Received job request: {request.id}, type: {request.type}")

        ret = messages_pb2.JobResponse(id=3342, type="dummy", result="This is a test")

        return ret


def serve():
    port = "50051"
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    messages_pb2_grpc.add_JobDispatchServicer_to_server(JobDispatchServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"Server started on port {port}")
    server.wait_for_termination()

if __name__ == "__main__":
    logging.basicConfig()
    serve()