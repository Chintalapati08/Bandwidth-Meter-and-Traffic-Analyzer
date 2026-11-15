from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import (
    MAIN_DISPATCHER,
    CONFIG_DISPATCHER,
    DEAD_DISPATCHER,
    set_ev_cls
)
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib import hub
from os_ken.lib.packet import packet, ethernet, ether_types

import csv
import os
import time


class SDNController(app_manager.OSKenApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SDNController, self).__init__(*args, **kwargs)

        self.datapaths = {}
        self.mac_to_port = {}

        os.makedirs("results", exist_ok=True)

        self.csv_file = "results/switch_stats.csv"

        # Create CSV file and write column headings
        with open(self.csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "switch_id",
                "table_id",
                "priority",
                "packet_count",
                "byte_count",
                "duration_sec"
            ])

        # Start periodic flow-statistics monitoring
        self.monitor_thread = hub.spawn(self._monitor)

        self.logger.info("SDN Controller Started")

    # Install a flow rule in the switch
    def add_flow(self, datapath, priority, match, actions):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions
        )

        datapath.send_msg(flow_mod)

    # Handle switch connection
    @set_ev_cls(
        ofp_event.EventOFPSwitchFeatures,
        CONFIG_DISPATCHER
    )
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.datapaths[datapath.id] = datapath

        self.logger.info(
            "Switch connected: %s",
            datapath.id
        )

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        # Table-miss rule: send unknown packets to controller
        match = parser.OFPMatch()

        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]

        self.add_flow(
            datapath,
            0,
            match,
            actions
        )

        self.logger.info("Table-miss flow installed")

    # Track switch connection and disconnection
    @set_ev_cls(
        ofp_event.EventOFPStateChange,
        [MAIN_DISPATCHER, DEAD_DISPATCHER]
    )
    def state_change_handler(self, ev):
        datapath = ev.datapath

        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath

        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)

    # Receive packets and perform MAC learning
    @set_ev_cls(
        ofp_event.EventOFPPacketIn,
        MAIN_DISPATCHER
    )
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath

        dpid = datapath.id
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None:
            return

        # Ignore LLDP packets
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src

        # Create MAC learning table for this switch
        self.mac_to_port.setdefault(dpid, {})

        # Learn the source MAC address
        self.mac_to_port[dpid][src] = in_port

        # Check whether destination MAC is known
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [
            parser.OFPActionOutput(out_port)
        ]

        # Install forwarding rule for known destinations
        if out_port != ofproto.OFPP_FLOOD:

            match = parser.OFPMatch(
                in_port=in_port,
                eth_dst=dst
            )

            self.add_flow(
                datapath,
                1,
                match,
                actions
            )

        # Forward packet through the switch
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=in_port,
            actions=actions,
            data=msg.data
        )

        datapath.send_msg(out)

        self.logger.info(
            "Packet forwarded: switch=%s src=%s dst=%s port=%s",
            dpid,
            src,
            dst,
            out_port
        )

    # Periodically request flow statistics
    def _monitor(self):
        while True:

            for datapath in list(self.datapaths.values()):

                parser = datapath.ofproto_parser

                request = parser.OFPFlowStatsRequest(
                    datapath
                )

                datapath.send_msg(request)

            hub.sleep(5)

    # Receive and save flow statistics
    @set_ev_cls(
        ofp_event.EventOFPFlowStatsReply,
        MAIN_DISPATCHER
    )
    def flow_stats_reply_handler(self, ev):

        datapath = ev.msg.datapath
        timestamp = time.time()

        with open(self.csv_file, "a", newline="") as f:

            writer = csv.writer(f)

            for stat in ev.msg.body:

                self.logger.info(
                    "Switch=%s Packets=%s Bytes=%s",
                    datapath.id,
                    stat.packet_count,
                    stat.byte_count
                )

                writer.writerow([
                    timestamp,
                    datapath.id,
                    stat.table_id,
                    stat.priority,
                    stat.packet_count,
                    stat.byte_count,
                    stat.duration_sec
                ])
