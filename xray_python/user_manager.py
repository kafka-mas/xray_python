import grpc
import logging
import uuid
import base64

from email_validator import validate_email, EmailNotValidError

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import DecodeError

from app.proxyman.command.command_pb2_grpc import HandlerServiceStub

from app.proxyman.command.command_pb2 import AddUserOperation, RemoveUserOperation, AlterInboundRequest, GetInboundUserRequest
from common.protocol.user_pb2 import User
from common.serial.typed_message_pb2 import TypedMessage
from proxy.vless.account_pb2 import Account


########################
### НАСТРОИТЬ ЛОГГЕР ###
########################
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

class UserManager:
    def __init__(self, channel: grpc.Channel):
        self._client = HandlerServiceStub(channel)
    
    def __create_account_typed_message(self, uid: str) -> TypedMessage:
        account = Account(id=uid, flow='xtls-rprx-vision', encryption='none')
        return TypedMessage(type='xray.proxy.vless.Account', value=account.SerializeToString())

    def __create_user_typed_message(self, email: str, account_tm: TypedMessage) -> TypedMessage: 
        user = User(level=0, email=email, account=account_tm)
        add_user = AddUserOperation(user=user)
        return TypedMessage(type='xray.app.proxyman.command.AddUserOperation', value=add_user.SerializeToString())

    def __is_email_strict(self, email) -> tuple[bool, str]:
        try:
            valid = validate_email(email)
            normalized_email = valid.email.lower()
            return True, normalized_email
        except EmailNotValidError as e:
            return False, str(e)

    def __is_uuid4(self, uuid_string) -> bool:
        try:
            uuid.UUID(uuid_string, version=4)
        except ValueError:
            return False
        return True

    def create(self, email: str, *, uid: str = None, tag: str = "main-inbound") -> dict:
        email_checked = self.__is_email_strict(email)
        if not email_checked[0]:
            raise ValueError(f"Wrong email address {email}!!!")
        email = email_checked[1]
        if uid is None:
            uid = str(uuid.uuid4())
        elif not self.__is_uuid4(uid):
            logging.info(f"Bad UUID ({uid}) format for {email}. New UUID was generated")
            uid = str(uuid.uuid4())
        try:
            account_typed_message = self.__create_account_typed_message(uid)
            user_typed_message = self.__create_user_typed_message(email, account_typed_message)
        except Exception as e:
            logging.exception(f"Failed to create protobuf messages for {email}, uid {uid}")
            raise

        alter_inbound_request = AlterInboundRequest(tag=tag, operation=user_typed_message)
        try:
            self._client.AlterInbound(alter_inbound_request)
            logging.info(f'Created user.  Email: {email}.  UUID: {uid}')
            return {"UUID": uid, "email": email}
        except grpc.RpcError as e:
            logging.error(f'Can\'t add user. {e}')
            raise
        except Exception as e:
            logging.exception(f"Unexpected error in create_user: {e}")
            raise
    
    def get(self, /, tag: str = "main-inbound", *, email: str = None) -> dict:
        try:
            users_request = GetInboundUserRequest(tag=tag, email=email)
            response = self._client.GetInboundUsers(users_request)
        except grpc.RpcError as e:
            logging.warning(f"Can't get user(s): {e}")
            return {}
        except Exception as e:
            logging.exception(f"Unexpected error in get_users: {e}")
            return {}
            
        response_dict = MessageToDict(response, always_print_fields_with_no_presence=True)
        for user in response_dict.get('users', []):
            account_info = user.get('account')
            if account_info and 'value' in account_info:
                try:
                    # Декодируем base64
                    binary_value = base64.b64decode(account_info['value'])
                    acc = Account()
                    acc.ParseFromString(binary_value)
                    # Преобразуем распакованный аккаунт в словарь
                    acc_dict = MessageToDict(acc)
                    # Заменяем base64-строку на словарь
                    account_info['value'] = acc_dict
                except (base64.binascii.Error, DecodeError) as e:
                # Логируем проблему для конкретного пользователя и оставляем поле как есть или ставим None
                    logging.warning(f"Failed to decode/parse account for user {user.get('email', 'unknown')}: {e}")
                    account_info['value'] = None
                except Exception as e:
                    logging.error(f"Unexpected error: {e}")
                    raise e

        return response_dict
    
    def remove(self, email: str, /, tag: str = "main-inbound") -> None:
        email_checked = self.__is_email_strict(email)
        if not email_checked[0]:
            raise ValueError(f"Wrong email address {email}!!!")
        email = email_checked[1]

        try:
            remove_user = RemoveUserOperation(email=email)
            remove_user_typed_message = TypedMessage(type='xray.app.proxyman.command.RemoveUserOperation', value=remove_user.SerializeToString())
            alter_inbound_request = AlterInboundRequest(tag=tag, operation=remove_user_typed_message)
            self._client.AlterInbound(alter_inbound_request)
            logging.info(f"Removed user {email}.")
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNKNOWN and "not found" in e.details().lower():
                logging.warning(f"User {email} not found in tag {tag}, nothing to remove (ignored).")
                return  
            logging.error(f'Can\'t remove user. {e}')
            raise
        except Exception as e:
            logging.exception(f"Unexpected error in remove_user: {e}")
            raise
