import subprocess

class RemotePinger:
    def __init__(self, host):
        self.host = host

    def ping(self, count=1, timeout=1000):
        """
        Ping the remote host.
        Returns True if the host is reachable, False otherwise.
        """
        try:
            output = subprocess.run(
                ["ping", "-n", str(count), "-w", str(timeout), self.host],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return output.returncode == 0
        except Exception as e:
            print(f"Ping failed: {e}")