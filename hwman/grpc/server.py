import uuid
import logging

import grpc
from concurrent import futures

from hwman.grpc.protobufs_compiled import jobs_pb2_grpc  # type: ignore
from hwman.grpc.protobufs_compiled.jobs_pb2 import (  # type: ignore
    JobType,
    JobStatus,
    Result,
    DataAxis,
    Job,
)
from hwman.grpc.protobufs_compiled.jobs_pb2_grpc import JobDispatchServicer  # type: ignore
from hwman.setup_measurements import execute_measurement
from hwman.measurements.dummy import generate_dummy_sweep


def dummy_measurement():
    sweep = generate_dummy_sweep()
    data_location, data = execute_measurement(sweep, "dummy_measurement")

    axes = []
    for ax in data.axes():
        axis = DataAxis(name=ax, values=list(int(x) for x in data[ax]["values"]))
        axes.append(axis)
    for dep in data.dependents():
        axis = DataAxis(
            name=dep,
            values=list(int(x) for x in data[dep]["values"]),
            depends_on=data[dep]["axes"],
        )
        axes.append(axis)
    result = Result(id=str(uuid.uuid4()), path=str(data_location), data=axes)
    return result


class JobService(JobDispatchServicer):
    def SubmitJob(self, request, context):
        # Process the job request and return a response
        print(f"Received job request: {request.id}, type: {request.type}")

        if request.type == JobType.JOB_TYPE_DUMMY:
            # Execute the dummy measurement
            result = dummy_measurement()
            ret = Job(
                id=request.id,
                user=request.user,
                type=request.type,
                status=JobStatus.JOB_STATUS_SUCCESS,
                payload=request.payload,
                result=result,
            )

        else:
            raise NotImplementedError(f"Job type {request.type} not implemented")

        return ret


def serve():
    port = "50051"
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    jobs_pb2_grpc.add_JobDispatchServicer_to_server(JobService(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"Server started on port {port}")
    server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig()
    serve()
