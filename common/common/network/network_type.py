import enum
import socket


class NetworkEnum(enum.Enum):
    TCP = "tcp"
    UDP = "udp"
    NONE = "none"


class NetworkHandler:
    def __init__(
        self, input_network_type: NetworkEnum, output_network_type: NetworkEnum
    ):
        self.input_network_type = input_network_type
        self.output_network_type = output_network_type

    def get_input_network_socket(self):
        return self.get_network_socket(self.input_network_type)

    def get_output_network_socket(self):
        return self.get_network_socket(self.output_network_type)

    def get_network_socket(self, network_type):
        if isinstance(network_type, str):
            print("Warning: network_type is str, converting to NetworkEnum")
            network_type = NetworkEnum(network_type)

        target_socket = None
        if network_type == NetworkEnum.TCP:
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            return target_socket
        elif network_type == NetworkEnum.UDP:
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            return target_socket
        else:
            return None
