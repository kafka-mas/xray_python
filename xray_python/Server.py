import grpc
import logging


########################
### НАСТРОИТЬ ЛОГГЕР ###
########################
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)


class Server:
    def __init__(self, *, address: str = "localhost", port: int = 10085, insecure: bool = False):   # добавить проверку на валидность адреса, добавить возможность вставить свой серт
        if insecure:
            self._channel = grpc.insecure_channel(f"{address}:{port}")
        else:
            credentials = grpc.ssl_channel_credentials()
            self._channel = grpc.secure_channel(f"{address}:{port}", credentials=credentials)
        
        from .user_manager import UserManager

        self._user_manager = UserManager(self._channel)
    
    def close(self) -> None:
        self._channel.close()

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False

    @property
    def users(self):
        return self._user_manager
