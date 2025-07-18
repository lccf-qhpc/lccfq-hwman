from hwman.client import Client, TestType


from instrumentserver.client.proxy import Client as cl



ins_c = cl()
params = ins_c.get_instrument("parameter_manager")
# params.fromFile("/home/pfafflab/Documents/github/lccfq-hwman/configs/parameter_manager-parameter_manager.json")

print("CHEKCING THAT IS HAS THE DAMN THING: ", params.qubit.f_ge())

# c.start()

c.start_test(TestType.POWER_RABI, "power rabi test thingy thing")
