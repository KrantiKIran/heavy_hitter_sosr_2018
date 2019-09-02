import os

class Config():
    
    def __init__(self, global_threshold=None, local_threshold=None):

        if global_threshold is None:
            self.global_threshold = 1000
        else:
            self.global_threshold = global_theshold

        self.threshold_dict = {}

        if local_threshold is None:
            self.default_local_threshold = 10000


    def add_dpid(self, datapath):
        for dpid in datapath:
            if self.threshold_dict.get(str(dpid)) is None:
                self.threshold_dict[str(dpid)] = {}

    def del_dpid(self, dpid):
        del self.threshold_dict[dpid]


    def update_threshold_values(self, dpid, key, value=None):

        # Updates the threshold dictionary, with local_threshold value if given,
	# otherwise with the default_local_threshold value for the specific key
	# as per the paper, different flows will have different thresholds
	# so as to reduce number of updation

        if value is None:
            value = self.default_local_threshold
        if self.threshold_dict.get(dpid) is None:
            self.threshold_dict[dpid] = {key : [self.global_threshold, 
                        int(value)]}
        else:
            self.threshold_dict[dpid][key] = [self.global_threshold, 
                        int(value)]

        for k in self.threshold_dict.keys():
            if k != dpid and self.threshold_dict[k].get(key) is None:
                self.threshold_dict[k] = {key : [self.global_threshold, 
                            self.default_local_threshold]}


    def fetch_config_stats(self, dpid=None, key=None):

        # Fetching the config stats for a given dpid and key value pair
	# all keys have a certain threshold based on their activity
	# that is stored in this dict (check HH paper for reference)
        try:
            result = self.threshold_dict[dpid][key]
        except:
		# returning the default threshold
            result = [self.global_threshold, self.default_local_threshold]

        return str(result)
