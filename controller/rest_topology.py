# Copyright (C) 2013 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json, subprocess, os

from ryu.app.wsgi import ControllerBase
from ryu.app.wsgi import Response
from ryu.app.wsgi import route
from ryu.app.wsgi import WSGIApplication
from ryu.base import app_manager
from ryu.lib import dpid as dpid_lib
from ryu.topology.api import get_switch, get_link, get_host

# REST API for switch configuration
#
# get all the switches
# GET /v1.0/topology/switches
#
# get the switch
# GET /v1.0/topology/switches/<dpid>
#
# get all the links
# GET /v1.0/topology/links
#
# get the links of a switch
# GET /v1.0/topology/links/<dpid>
#
# get all the hosts
# GET /v1.0/topology/hosts
#
# get the hosts of a switch
# GET /v1.0/topology/hosts/<dpid>
#
# where
# <dpid>: datapath id in 16 hex

def get_scp_command():
    return "sudo sshpass -p \"vm1\" scp -o ConnectTimeout=3 -o StrictHostKeyChecking=no "

def get_ssh_command():
    return "sudo sshpass -p \"vm1\" ssh -o StrictHostKeyChecking=no "
######################################################
##Commmds to obtain usernames
def get_username():
    return "root"
######################################################


def getDictFrom(filename):
		file_handler=open(filename,"r")
		variable=json.load(file_handler)
		file_handler.close()
		return(variable)

def getRemoteDictFrom(ip):
	filename = "/root/aloe_work/AWS/common/LOG/stats/neighbor_list.json"
	print(ip)
	CMD="%s %s@%s:%s /tmp" %("sshpass -p \"vm1\" scp -o ConnectTimeout=3 -o StrictHostKeyChecking=no ","root",ip,
						filename)
	proc = subprocess.Popen(CMD,shell=True, stdout=subprocess.PIPE)
	(out, err) = proc.communicate()
	targetFile=os.path.basename(filename)	
	variable = getDictFrom("/tmp/%s"%(targetFile))
	return(variable)

def runLLDPCommand(ip,host_name, sub_command, visited, flag=0):
	Sys_IP = "192.168.1.%s"%(re.findall(r'\d+', host_name)[0])

	CMD="%s %s@%s \"%s\""%(get_ssh_command(), get_username(), Sys_IP, sub_command)
	proc = subprocess.Popen(CMD,shell=True, stdout=subprocess.PIPE)
	(out, err) = proc.communicate()
	#print out
	output_split=out.split("\n")
	# listofMacPos=[i for i,j in enumerate(output_split) if "PortID:" in j]
	# listofIfacePos=[i for i,j in enumerate(output_split) if "Interface:" in j]
	listofSysname=[i for i,j in enumerate(output_split) if "SysName:" in j]
	listofIfacePos = [i-3 for i in listofSysname]
	listofMacPos = [i+9 for i in listofSysname]

	neighbor_List_full_details=[]
	neighbor = {}

	neighbor_SysName = []
	neighborIPList = []

	for i,j in enumerate(listofMacPos):
		neighbor_dets = {}
		ifaceLine=output_split[listofIfacePos[i]]
		macLine=output_split[j]
		sysLine=output_split[listofSysname[i]]
		
		iface=re.split(': |, ',ifaceLine)[1].strip()
		mac=re.split(': |, ',macLine)[1].strip().replace("mac ","")
		# print(mac)
		SysName=re.split(': |, ',sysLine)[1].strip()
		#print SysName
		if ("eth" in iface):
			neighbor[iface]="192.168.1.%s"%(re.findall(r'\d+', SysName)[0])
			neighbor_dets["src"] = {}
			neighbor_dets["src"]["iface"] = iface
			neighbor_dets["src"]["ip"] = Sys_IP
			neighbor_dets["src"]["name"] = host_name
			neighborIPList.append(neighbor[iface])
			neighbor_SysName.append(SysName)
			neighbor_dets["dst"] = {}
			neighbor_dets["dst"]["ip"] = neighbor[iface]
			neighbor_dets["dst"]["mac"] = mac
			neighbor_dets["dst"]["name"] = SysName

			neighbor_List_full_details.append(neighbor_dets)

		if flag == 0:
			for i in range(len(neighborIPList)):
				new_command = "%s %s@%s \"lldpcli show neighbors\""%(get_ssh_command(), get_username(), neighborIPList[i])
				try:
					visited.index(neighbor_SysName[i]) 
				except ValueError:
					visited.append(neighbor_SysName[i])
					neighbor_List_full_details = neighbor_List_full_details + \
												runLLDPCommand(Sys_IP, neighbor_SysName[i],\
															new_command, visited, flag=1)
	# print(host_name)
	return(neighbor_List_full_details)


class TopologyAPI(app_manager.RyuApp):
	_CONTEXTS = {
		'wsgi': WSGIApplication
	}

	def __init__(self, *args, **kwargs):
		super(TopologyAPI, self).__init__(*args, **kwargs)

		wsgi = kwargs['wsgi']
		wsgi.register(TopologyController, {'topology_api_app': self})


class TopologyController(ControllerBase):
	def __init__(self, req, link, data, **config):
		super(TopologyController, self).__init__(req, link, data, **config)
		self.topology_api_app = data['topology_api_app']

	@route('topology', '/v1.0/topology/switches',
		   methods=['GET'])
	def list_switches(self, req, **kwargs):
		return self._switches(req, **kwargs)

	@route('topology', '/v1.0/topology/switches/{dpid}',
		   methods=['GET'], requirements={'dpid': dpid_lib.DPID_PATTERN})
	def get_switch(self, req, **kwargs):
		return self._switches(req, **kwargs)

	@route('topology', '/v1.0/topology/links',
		   methods=['GET'])
	def list_links(self, req, **kwargs):
		return self._links(req, **kwargs)

	@route('topology', '/v1.0/topology/links/{dpid}',
		   methods=['GET'], requirements={'dpid': dpid_lib.DPID_PATTERN})
	def get_links(self, req, **kwargs):
		return self._links(req, **kwargs)

	@route('topology', '/v1.0/topology/hosts',
		   methods=['GET'])
	def list_hosts(self, req, **kwargs):
		return self._hosts(req, **kwargs)

	@route('topology', '/v1.0/topology/hosts/{dpid}',
		   methods=['GET'], requirements={'dpid': dpid_lib.DPID_PATTERN})
	def get_hosts(self, req, **kwargs):
		return self._hosts(req, **kwargs)

	##from this point all commnands are customized reoute commnds designed for vm systems
	@route('topology', '/v1.0/topology/neighbors', 
			methods=['GET'], requirements={'dpid': dpid_lib.DPID_PATTERN})
	def list_neighbors(self, req, **kwargs):
		return self._neighbors(req, **kwargs)
	
	@route('topology', '/v1.0/topology/get_island/{host_name}', 
			methods=['GET'], requirements={'dpid': dpid_lib.DPID_PATTERN})
	def get_island(self, req, **kwargs):
		return self._island(req, **kwargs)

	def _switches(self, req, **kwargs):
		dpid = None
		if 'dpid' in kwargs:
			dpid = dpid_lib.str_to_dpid(kwargs['dpid'])
		switches = get_switch(self.topology_api_app, dpid)
		body = json.dumps([switch.to_dict() for switch in switches])
		return Response(content_type='application/json', body=body)

	def _links(self, req, **kwargs):
		dpid = None
		if 'dpid' in kwargs:
			dpid = dpid_lib.str_to_dpid(kwargs['dpid'])
		links = get_link(self.topology_api_app, dpid)
		body = json.dumps([link.to_dict() for link in links])
		return Response(content_type='application/json', body=body)

	def _hosts(self, req, **kwargs):
		dpid = None
		if 'dpid' in kwargs:
			dpid = dpid_lib.str_to_dpid(kwargs['dpid'])
		hosts = get_host(self.topology_api_app, dpid)
		body = json.dumps([host.to_dict() for host in hosts])
		return Response(content_type='application/json', body=body)

	def _neighbors(self, req, **kwargs):
		dpid = None
		neighbors = {}
		neighbors["controller_self"] = getDictFrom("/root/aloe_work/neighbor_list.json")
		var = neighbors["controller_self"]
		for links in var.keys():
			neighbors["controller_%s"%(links)] = getRemoteDictFrom(var[links])
		body = json.dumps(neighbors)
		return Response(content_type='application/json', body=body)
	
	def __island(self, req, **kwargs):
		dpid = None
		host_name = kwargs['host_name']
		print("Self:")
		print(self)

		print("host_name:")
		print(host_name)

		visited = []
		body = json.dumps(runLLDPCommand(host_name=host_name, sub_command="lldpcli show neighbors", visited=visited, ip=None))
		return Response(content_type='application/json', body=body)

