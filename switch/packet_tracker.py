# This file is run in the switches to track the flow and also computes a 
# hash and is supposed to send the hash along with the flow data to the controller


from __future__ import print_function
import datetime,subprocess,sys,os,json
import time,hashlib
import os,sys
import requests,json
import xmlrpclib
#################################################

###The local threshold parameter
# this will denote the new threshold for a HH flow
alpha = 2

# the controller connects to this switch at this port
# to collect data regarding the flows
client = xmlrpclib.ServerProxy('http://10.5.20.124:9009/')


def get_flow_det(flow):
    flow_det_1 = flow.split(',')
    flow_det = []
    for flow_temp in flow_det_1:
        temp_list = flow_temp.split(' ')
        for temp in temp_list:
            if len(temp) != 0:
                flow_det.append(temp)
    flow_dict = {}
    for flow_param in flow_det:
        flow_param_1 = flow_param.split('=')

        # This helps us omit the list element which has no '='
        # for example,'tcp'
        if len(flow_param_1) > 1:     
            flow_dict[flow_param_1[0]] = flow_param_1[1]
    return flow_dict
    
# The function to get the dump flows, this uses the subprocess library to 
# get all the flow data
# Returns a dictionary of flow value to the hash key
def getFlowDump():
    # getting flow raw data dump for switch S1
    command = "ovs-ofctl dump-flows s"+sys.argv[1]
    proc = subprocess.Popen(command,shell=True, stdout=subprocess.PIPE
                            ,stderr=subprocess.PIPE)
    (out, err) = proc.communicate()

    if err:
        pass

    flow_list = out.split('\n')
    flow_dict = {}
    del flow_list[0]

    if len(flow_list) > 0:
        del flow_list[len(flow_list)-1]

    for flow in flow_list:
        flow_det = get_flow_det(flow)

        if flow_det['priority'] == '1':
            packet_count = flow_det['n_packets']
            print("Packet count: "+packet_count)
            key = getFlowHash(flow_det)
            flow_dict[key] = packet_count

        with open("s"+sys.argv[1]+"stats.txt", "a+") as wr:
            wr.write(str(flow_dict))
            wr.write("\n")

    # returns a dict of flow data
    # flowkey, packet count
    return flow_dict


# The function to calculate the hash value based on the 5 components of the flow
# At the moment just calculates using the src mac address, the destination mac address and the 'in' port
def getFlowHash(flow_hash):
    if flow_hash['in_port'] == 'LOCAL':
        flow_hash['in_port'] = 'fffffffe'

    hash_str = flow_hash['dl_src'] + flow_hash['dl_dst'] + flow_hash['in_port']

    with open("s"+sys.argv[1]+"stats.txt", "a+") as wr:
        wr.write("src -> "+flow_hash['dl_src']+" dst -> "+flow_hash['dl_dst']+" in_port -> "+flow_hash['in_port']+"\n")
        wr.write("Hash_Str: "+hash_str+"\n")

    hash_dict = hashlib.sha384(hash_str.encode())
    key = hash_dict.hexdigest()
    return key[0:len(key)/3]#The len(key)/3 has been taken to keep the 
    # length of the hash key under check and has no significance

# A function to check if the flow is a local heavy hitter
def checkLocalThreshold(flow_dict):

    local_heavy_hitter = {}

    for key in flow_dict.keys():

    # fetching the current threshold for the key
        threshold = eval(client.fetch(sys.argv[1], key))

    # if number of packets exceeds current threshold
    # send current number of packets
    # else, don't update anything
    # just send current threshold value

        if int(flow_dict[key],10) > threshold[1]:
            local_heavy_hitter[key] = flow_dict[key]

        else:
            local_heavy_hitter[key] = threshold[1]
    
    return local_heavy_hitter
            

def sendPacketCount(hh):

    # sends data to server in the format -> k1-c1,k2-c2,
    # Where k_i is the ith key, and c_i is the ith count, id is the dpid
    # here server = controller
    # the function updatestats is present in hh_app.py

    print({sys.argv[1] : hh})
    key_string = ""
    for key, value in hh.items():
        key_string = key_string + str(key) + "-" + str(value) + ","
    print(key_string)
    return client.updatestats(sys.argv[1], key_string)

# the new threshold function
# this can be changed to any other mathematical function
def new_threshold(old):
    new = old * alpha
    return new

def main():
    # get all flow details at time t
    flow_dict = getFlowDump()

    # for all flows, check if a flow has exceeded the local threshold
    heavy_hitter = checkLocalThreshold(flow_dict)

    # status.txt = keeps a log of the switch flow data
    # this portion is for logging only
    with open("./status.txt", "a+") as wr:
        wr.write("Status for switch s"+sys.argv[1]+" ...\n")
        for key, value in heavy_hitter.items():
            wr.write(str(key)+"   "+str(value))
            wr.write("\n")

        wr.write("\n")

    # getting list of true heavy hitters
    # converting the return type to list
    result = eval(sendPacketCount(heavy_hitter))
    print(result)

    for k in result:

    # Fetching the threshold statistics using XMLRPC call
    # sys.argv[1] = switch ID

    # fetching threshold for current flow
        threshold = eval(client.fetch(sys.argv[1], k))
        print("Threshold: "+str(threshold))

        new = new_threshold(threshold[1])
        print("NewThreshold: "+str(new))

    # updating the new threshold value at the server
    # and updating the threshold list in server
        client.update_threshold(sys.argv[1], k, str(new))

    # Removing non-heavy hitter keys from the flow dictionary
    for k in flow_dict.keys():
        if k not in result:
            flow_dict.pop(k)

    print("Heavy Hitter: "+str(flow_dict)) 


if __name__ == '__main__':
    while True:
        time.sleep(3)
        main()
    
