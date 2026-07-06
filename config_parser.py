import socket
import urllib.request
import os

OBFUSCATION_KEYS = {
    'jc', 'jmin', 'jmax', 
    's1', 's2', 's3', 's4', 
    'h1', 'h2', 'h3', 'h4', 
    'i1', 'i2', 'i3', 'i4', 'i5'
}


class WGConfig:
    def __init__(self, interface, peers):
        self.interface = interface
        self.peers = peers

    @classmethod
    def parse(cls, filepath):
        interface = {}
        peers = []
        current_section = None
        current_dict = None

        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if line.startswith('[') and line.endswith(']'):
                    section_name = line[1:-1].lower()
                    if section_name == 'interface':
                        current_section = 'interface'
                        current_dict = interface
                    elif section_name == 'peer':
                        current_section = 'peer'
                        peer = {}
                        peers.append(peer)
                        current_dict = peer
                    else:
                        current_section = None
                        current_dict = None
                    continue

                if current_dict is not None and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    current_dict[key] = value

        return cls(interface, peers)

    def write_variant(self, output_path, obf_params, testing_mode=False):
        """Writes a config variant with obfuscation parameters and optional test routing."""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("[Interface]\n")
            for k, v in self.interface.items():
                if k.lower() in OBFUSCATION_KEYS:
                    continue
                f.write(f"{k} = {v}\n")

            # Write new obfuscation params
            for k, v in obf_params.items():
                f.write(f"{k} = {v}\n")

            f.write("\n")

            for peer in self.peers:
                f.write("[Peer]\n")
                for k, v in peer.items():
                    if testing_mode and k.lower() == 'persistentkeepalive':
                        pass # Ignore existing keepalive in testing mode
                    else:
                        f.write(f"{k} = {v}\n")
                if testing_mode:
                    f.write("PersistentKeepalive = 1\n")
                f.write("\n")

    def write_winning(self, output_path, obf_params):
        """Writes the final winning config without touching routing."""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("[Interface]\n")
            for k, v in self.interface.items():
                if k.lower() in OBFUSCATION_KEYS:
                    continue
                f.write(f"{k} = {v}\n")

            for k, v in obf_params.items():
                f.write(f"{k} = {v}\n")

            f.write("\n")

            for peer in self.peers:
                f.write("[Peer]\n")
                for k, v in peer.items():
                    f.write(f"{k} = {v}\n")
                f.write("\n")
