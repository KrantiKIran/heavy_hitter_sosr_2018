# Network Heavy Hitter Detector
A Heavy Hitter is the term that is given to the heaviest flow that crosses a hop distance of 3. This application runs on a SDN framework where each controller polls the switches for flow statistics and then the stats are analysed.
It is however possible to extend this application to any quantifiable property of network flows and not just Heavy Hitter detection. 

Below is a gist of the detection procedure

![HH_App](/images/heavy_hitter.png)

This work is based on the work by Harrison et al. on [Network-Wide Heavy Hitter Detection](https://dl.acm.org/doi/abs/10.1145/3185467.3185476), that was published in Symposium on SDN Research 2018.

Our work has been tested using [mininet](http://mininet.org/) SDN emulator and the [RYU](https://osrg.github.io/ryu/) SDN controller. 

### Switch

        cd switch
        sudo python3 packet_tracker <switch_number>

### Controller

        cd controller
        ryu-manager hh_app rest_topology
For RYU installation, you may use pip
    pip install ryu
or by source
    git clone git://github.com/osrg/ryu.git
    cd ryu; python ./setup.py install