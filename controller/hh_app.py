from operator import attrgetter

from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_0
from ryu.lib.mac import haddr_to_bin
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.controller.controller import Datapath as dpth
from ryu.lib import hub
import simple_switch_13_timeout

from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.client import Binary

import datetime
import ryu.lib.ofctl_v1_3 as ofctl
import requests
import os,sys, json
import hashlib
import time

from config import Config

#alpha = 0.5

class HeavyHitterDetect(simple_switch_13_timeout.SimpleSwitch13):

    def __init__(self, *args, **kwargs):
        super(HeavyHitterDetect, self).__init__(*args, **kwargs)
        # importing all functions from config file
        self.config_obj = Config()
        self.datapaths = {}
        self.GLOBAL_THRESHOLD = self.config_obj.global_threshold

        # this will run the polling method in a background thread
        self.monitor_thread = hub.spawn(self._hhapp)

        # running the XMLRPC in background
        server = SimpleXMLRPCServer(('0.0.0.0', 9009),
                                logRequests=False,
                                allow_none=True)

        server.register_introspection_functions()
        server.register_multicall_functions()

        # registering XMLRPC functions
        server.register_instance(self)
        server.register_function(self.updatestats, "updatestats")
        server.register_function(self.config_obj.update_threshold_values,
            "update_threshold")
        server.register_function(self.config_obj.fetch_config_stats, "fetch")

        self.key_stats = {}
        self.mac_key_stats = {}

        # xmlrpc commands that have to be run in a separate thread
        # the spawn function creates a new thread
        # normal threading does not work here
        self.new_thread = hub.spawn(server.serve_forever)

    def self.update_key_stats(self):
        session = requests.Session()
        session.trust_env = False
        for dpid in self.datapaths:
            URL = "http://10.5.20.234:9777/getFlow/s%s"%(dpid)
            r = session.get(URL)

    def _estimate_calc(self, k):
        # this data is fetched continuously
        # in the background by _update_poll_stats
        print("")
        print("Self Datapaths :" + str(self.datapaths) )
        dic = self.update_key_stats()
        result = 0
        for dpid in dic.keys():
            try:
                result += int(dic[dpid][k])
            except:
                pass

        return result

        # not used currently
    def _ewma_calc(self, config, key_stats, dpid, key, alpha):

        #There may not be report for a key from every switch
        try:
            result = (1-alpha)*(config[dpid][key][1]) + alpha*int(key_stats[dpid][key])
        except:
            result = (1-alpha)*(config[dpid][key][1])
        return result

        # not used currently
    def _reset_threshold(self, config, key_stats, key, alpha):

        for i in config.keys():
            num = self._ewma_calc(config, key_stats, i, key, alpha)
            den = 0
            total = 0
            for j in config.keys():
                parts = self._ewma_calc(config, key_stats, j, key, alpha)
                den += parts
                try:
                    total += int(key_stats[j][key])
                except:
                    pass

            frac = num/den
            #print(frac)

            try:
                t = int(frac * (self.config_obj.global_threshold - total) + int(key_stats[j][key]))
            except:
                t = int(frac * (self.config_obj.global_threshold - total))

            #print("T: "+str(t))

            self.config_obj.update_threshold_values(i, key, str(t))

            # the main function
    def updatestats(self, dpid, data):
        #Stores the estimate sum
        estimate = {}
        #Maintains the switch-key statistics
        stats = {}
        #Maintains the list of heavy hitter keys
        hh_keys = []
        #Data in the format: k1-v1,k2-v2,...,kN-vN,
        #print("Config dictionary: "+str(self.config_obj.threshold_dict))
        arr = data.split(",")
        #print("Arr: "+str(arr))

        # calculating estimated sum of packet count for a key
        #print(data)

        true_hh = {}

        for item in arr:

            # item = each key and count pair

            if item != "":

                # the entire data comes in the format of a comma seperated string
                # so now we are splitting the string

                key = item.split("-")[0]
                #print("Key: "+key)

                # this is a local call
                # fetching threshold for the given key
                threshold = eval(self.config_obj.fetch_config_stats(dpid, key))

                #print("Threshold values for switch "+dpid+" :"+str(threshold))
                self.GLOBAL_THRESHOLD = threshold[0]
                self.LOCAL_THRESHOLD = threshold[1]
                '''
                if self.LOCAL_THRESHOLD == self.config_obj.default_local_threshold:
                    self.config_obj.update_threshold_values(dpid, key)
                '''

                value = item.split("-")[1]
                #print("Value: "+value)

                # storing the packet count for a key
                # at a particular switch

                if stats.get(dpid) is None:
                    stats[dpid] = {key : value}
                else:
                    stats[dpid][key] = value

                # calculating estimated sum of packet count for a key

                estimate[key] = int(value)

                for k in self.datapaths:
                    k = str(k)
                    if k != dpid:
                        stats[k] = {key : str(self.LOCAL_THRESHOLD - 1)}
                        estimate[key] += int(stats[k][key])

        #print("Stats: "+str(stats))
        #print("Estimate: "+str(estimate))

        '''
        An example of statistics printed out for switch s1:

        Arr: ['2de978efdee8d4610e7d8bde5d7941e7-10196777', 'e683a615fc57c62217478c9498357398-21887207', '']

        Key: 2de978efdee8d4610e7d8bde5d7941e7
        Value: 10196777

        Key: e683a615fc57c62217478c9498357398
        Value: 21887207

        Stats: {'4': {'e683a615fc57c62217478c9498357398': '9999'}, '2': {'e683a615fc57c62217478c9498357398': '9999'}, '1': {'2de978efdee8d4610e7d8bde5d7941e7': '10196777', 'e683a615fc57c62217478c9498357398': '21887207'}, '3': {'e683a615fc57c62217478c9498357398': '9999'}}

        Estimate: {'2de978efdee8d4610e7d8bde5d7941e7': 10226774, 'e683a615fc57c62217478c9498357398': 21917204}
        '''

        # checking if estimated sum exceeds global threshold

        for k in estimate.keys():
            # if the estimated sum exceeds,
            # then the actual packet count is fetched
            # and the current packet count is calculated
            if estimate[k] > self.GLOBAL_THRESHOLD:
                estimate[k] = self._estimate_calc(k)
                #Final estimate check after polling
                if estimate[k] > self.GLOBAL_THRESHOLD:
                    #print("The values of k is "+ str(k))
                    hh_keys.append(k)
        '''
        for k in hh_keys:
            self._reset_threshold(self.config_obj.threshold_dict,
                self.key_stats, k, alpha)
        '''

        # for every heavy hitter,
        # we are printing the mac address of the heavy hitter
        # to understand the source of the HH

        for k in self.mac_key_stats.keys():
            for hh_key in hh_keys:
                if hh_key in self.mac_key_stats[k]:
                    print("True heavy hitter: "+k+ " : "+hh_key)

                    hh_dict = {'hh_hash':hh_key, 'time':(int)(time.time())}
                    snc_ip = "http://10.5.20.124:8989/send_heavy_hitter_data"
                    requests.post(snc_ip, data = hh_dict)

        return str(hh_keys)

    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath

        # adding new switch to the list
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
                #Adding the new dpid key
                self.config_obj.add_dpid(self.datapaths)

        # DEAD_DISPATCHER means a switch is down
        # so it is removed from the list
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]
                #Deleting the dpid key
                self.config_obj.del_dpid(datapath.id)

    def _hhapp(self):
        while True:
            for dp in self.datapaths.values():
                # requesting stats from the switches
                self._request_stats(dp)
            hub.sleep(1)    #Request stats after every 1 second

    def _request_stats(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    def _getFlowHash(self, flow_hash):
        if flow_hash['in_port'] == 'LOCAL':
            flow_hash['in_port'] = 'fffffffe'
        hash_str = str(flow_hash['eth_src']) + str(flow_hash['eth_dst']) + str(flow_hash['in_port'])
        hash_dict = hashlib.sha384(hash_str.encode())
        key = hash_dict.hexdigest()
        end = int(len(key)/3)

        # returning portion of key and the mac address (source of HH)
        return key[0:end], str(flow_hash['eth_src'])

    def _update_poll_stats(self, dpid, k, count):
        #Continuously updates the poll statistics to the key_status dictionary
        if self.key_stats.get(dpid) is None:
            self.key_stats[dpid] = {k : count}
        else:
            self.key_stats[dpid][k] = count

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        body = ev.msg.body
        for stat in sorted([flow for flow in body if flow.priority == 1],
                           key=lambda flow: (flow.match['in_port'],
                                             flow.match['eth_dst'],
                                             flow.match['eth_src'])):
            k, src= self._getFlowHash(stat.match)

            # appending the mac address to the key
            # so that we can understand where the HH came from

            if self.mac_key_stats.get(src) is None:
                self.mac_key_stats[src] = []
            elif k not in self.mac_key_stats[src]:
                self.mac_key_stats[src].append(k)
            
            self._update_poll_stats(str(ev.msg.datapath.id), k, stat.packet_count)
