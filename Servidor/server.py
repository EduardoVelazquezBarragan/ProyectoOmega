import grpc
from concurrent import futures
import threading
import time
import json
import uuid
import jwt  # Asegurarse de que sea PyJWT
from datetime import datetime, timedelta, timezone

import turbomessage_pb2
import turbomessage_pb2_grpc

# Paths para persistencia
USERS_FILE = 'users.json'
MAILS_FILE = 'mails.json'
MAX_INBOX = 5
MAX_OUTBOX = 5

# JWT configuration
JWT_SECRET = 'tu_clave_secreta_super_segura'
JWT_ALGORITHM = 'HS256'
JWT_EXP_HOURS = 1

lock = threading.Lock()

# Estado en memoria
state = {
    'users': {},       # username -> {password, id}
    'inbox': {},       # username -> [mail_id,...]
    'outbox': {},      # username -> [mail_id,...]
    'mails': {}        # mail_id -> mail_object
}

# Utilerías de persistencia
def load_state():
    try:
        with open(USERS_FILE, 'r') as f:
            state['users'] = json.load(f)
    except FileNotFoundError:
        state['users'] = {}
    try:
        with open(MAILS_FILE, 'r') as f:
            data = json.load(f)
            state['mails'] = data.get('mails', {})
            state['inbox'] = data.get('inbox', {})
            state['outbox'] = data.get('outbox', {})
    except FileNotFoundError:
        state['mails'] = {}
        state['inbox'] = {}
        state['outbox'] = {}


def save_state():
    with open(USERS_FILE, 'w') as f:
        json.dump(state['users'], f)
    with open(MAILS_FILE, 'w') as f:
        data = {
            'mails': state['mails'],
            'inbox': state['inbox'],
            'outbox': state['outbox']
        }
        json.dump(data, f)

class TurboMessageServicer(turbomessage_pb2_grpc.TurboMessageServicer):
    def _validate_token(self, token, context):
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload['sub']
        except jwt.ExpiredSignatureError:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, 'Token expirado')
        except jwt.InvalidTokenError:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, 'Token inválido')

    def Register(self, request, context):
        with lock:
            if request.username in state['users']:
                return turbomessage_pb2.RegisterResponse(
                    success=False,
                    message='Usuario ya existe'
                )
            user_id = str(uuid.uuid4())
            state['users'][request.username] = {
                'password': request.password,
                'id': user_id
            }
            state['inbox'][request.username] = []
            state['outbox'][request.username] = []
            save_state()
            return turbomessage_pb2.RegisterResponse(success=True, message='Registrado exitosamente')

    def Login(self, request, context):
        user = state['users'].get(request.username)
        if not user or user['password'] != request.password:
            return turbomessage_pb2.LoginResponse(success=False, message='Credenciales inválidas')
        payload = {
            'sub': request.username,
            'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HOURS)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return turbomessage_pb2.LoginResponse(success=True, token=token, message='Login exitoso')

    def SendMessage(self, request, context):
        sender = self._validate_token(request.token, context)
        receiver = request.to
        with lock:
            if receiver not in state['users']:
                return turbomessage_pb2.SendMessageResponse(success=False, message='Usuario receptor no existe')
            if len(state['outbox'][sender]) >= MAX_OUTBOX:
                return turbomessage_pb2.SendMessageResponse(success=False, message='Bandeja de salida llena')
            if len(state['inbox'][receiver]) >= MAX_INBOX:
                return turbomessage_pb2.SendMessageResponse(success=False, message='Bandeja de entrada del receptor llena')
            mail_id = str(uuid.uuid4())
            mail = {
                'id': mail_id,
                'sender': sender,
                'to': receiver,
                'subject': request.subject,
                'body': request.body,
                'read': False
            }
            state['mails'][mail_id] = mail
            state['outbox'][sender].append(mail_id)
            state['inbox'][receiver].append(mail_id)
            save_state()
            return turbomessage_pb2.SendMessageResponse(success=True, message='Mensaje enviado')

    def ListInbox(self, request, context):
        user = self._validate_token(request.token, context)
        for mail_id in state['inbox'].get(user, []):
            mail = state['mails'][mail_id]
            yield turbomessage_pb2.Message(
                id=mail['id'], sender=mail['sender'], to=mail['to'],
                subject=mail['subject'], body=mail['body'], read=mail['read']
            )

    def ReadMessage(self, request, context):
        user = self._validate_token(request.token, context)
        mail_id = request.message_id
        with lock:
            if mail_id not in state['inbox'].get(user, []) and mail_id not in state['outbox'].get(user, []):
                context.abort(grpc.StatusCode.NOT_FOUND, 'Mensaje no encontrado')
            mail = state['mails'][mail_id]
            if mail_id in state['inbox'][user] and not mail['read']:
                mail['read'] = True
                save_state()
            return turbomessage_pb2.ReadMessageResponse(
                message=turbomessage_pb2.Message(
                    id=mail['id'], sender=mail['sender'], to=mail['to'],
                    subject=mail['subject'], body=mail['body'], read=mail['read']
                )
            )
        
    def ListOutbox(self, request, context):
        user = self._validate_token(request.token, context)
        for mail_id in state['outbox'].get(user, []):
            mail = state['mails'][mail_id]
            yield turbomessage_pb2.Message(
                id=mail['id'],
                sender=mail['sender'],
                to=mail['to'],
                subject=mail['subject'],
                body=mail['body'],
                read=mail['read']
            )

    def DeleteMessage(self, request, context):
        user = self._validate_token(request.token, context)
        mail_id = request.message_id
        with lock:
            removed = False
            for box in ['inbox', 'outbox']:
                if mail_id in state[box].get(user, []):
                    state[box][user].remove(mail_id)
                    removed = True
            if removed:
                save_state()
                return turbomessage_pb2.DeleteMessageResponse(success=True, message='Mensaje borrado')
            else:
                context.abort(grpc.StatusCode.NOT_FOUND, 'Mensaje no encontrado')

# Arranque del servidor
def serve():
    load_state()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    turbomessage_pb2_grpc.add_TurboMessageServicer_to_server(TurboMessageServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print('Servidor gRPC escuchando en 50051')
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        print('Deteniendo servidor...')
        server.stop(0)

if __name__ == '__main__':
    serve()
