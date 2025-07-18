
from hwman.client import Client

from hwman.grpc.protobufs_compiled.test_pb2 import TestType

from instrumentserver.client.proxy import Client as cl

c = Client(address="128.174.248.42", port=50001)

ins_c = cl()
params = ins_c.get_instrument("parameter_manager")
params.fromFile("/home/pfafflab/Documents/github/lccfq-hwman/configs/parameter_manager-parameter_manager.json")


c.start()
c.start_test(TestType.RESONATOR_SPEC, "test_1")



