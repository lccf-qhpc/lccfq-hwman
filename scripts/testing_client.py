
from hwman.client.client import Client

if __name__ == "__main__":
    client = Client(clients_cert_dir="/home/pfafflab/Documents/github/lccfq-hwman/certs/clients",
                    ca_cert_path="/home/pfafflab/Documents/github/lccfq-hwman/certs/ca.crt")
    ret = client.ping_server()
    print(ret)

    ret = client.start_res_spec()
    print("res_spec done")
    import pprint
    pprint.pprint(ret)
    # ret = client.start_res_spec_vs_gain()
    # print("res_spec_vs_gain done")
    # ret = client.start_sat_spec()
    # print("sat_spec done")
    # ret = client.start_power_rabi()
    # print("power rabi done")
    # ret = client.start_pi_spec()
    # print("pi spec done")
    # ret = client.start_res_spec_after_pi()
    # print("res spec after pi done")
    # ret = client.start_t1()
    # print("t1 done")
    # ret = client.start_t2r()
    # print("t2r done")
    # ret = client.start_t2e()
    # print("t2e done")
    # ret = client.start_ro_cal()
    # print("rocal done")
    # print(ret)
    # print("all done baby")
    #

    # ret = client.start_tuneup_protocol()

