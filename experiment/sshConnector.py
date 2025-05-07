from fabric import Connection, Config

class SSHConnector(object):
    def __init__(self, management_ip, local_ip, user, key_filename):
        self.management_ip = management_ip
        self.local_ip = local_ip
        self.user = user
        self.conf = Config()
        self.conf.connect_kwargs = {"key_filename": [key_filename]}
        self.connection = None

    def get_connection(self):
        if not self.connection:
            print(f"New SSH connection for: {self.management_ip}")
            self.connection = Connection(host=self.management_ip,
                                user=self.user,
                                config=self.conf)
            self.connection.open()
        return self.connection

    def reset_connection(self):
        try:
            self.connection.close()
        except:
            pass
        self.connection = None

    def start_connection(self):
        if not self.connection:
            print(f"New SSH connection for: {self.management_ip}")
            self.connection = Connection(host=self.management_ip,
                                user=self.user,
                                config=self.conf)
            self.connection.open()
