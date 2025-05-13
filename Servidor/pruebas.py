# test_server.py
import grpc
import turbomessage_pb2
import turbomessage_pb2_grpc

def main():
    # Conexión al servidor
    channel = grpc.insecure_channel('localhost:50051')
    stub = turbomessage_pb2_grpc.TurboMessageStub(channel)

    # 1. Registro de usuarios
    print("== Registro ==")
    r1 = stub.Register(turbomessage_pb2.RegisterRequest(username='alice', password='secret'))
    print("Alice:", r1)
    r2 = stub.Register(turbomessage_pb2.RegisterRequest(username='bob',   password='pwd'))
    print("Bob:  ", r2)

    # 2. Login y obtención de token
    print("\n== Login ==")
    login_alice = stub.Login(turbomessage_pb2.LoginRequest(username='alice', password='secret'))
    print("Alice login:", login_alice)
    token_alice = login_alice.token

    login_bob = stub.Login(turbomessage_pb2.LoginRequest(username='bob', password='pwd'))
    print("Bob login:  ", login_bob)
    token_bob = login_bob.token

    # 3. Envío de mensaje de Alice a Bob
    print("\n== SendMessage ==")
    send_resp = stub.SendMessage(
        turbomessage_pb2.SendMessageRequest(
            token=token_alice,
            to='bob',
            subject='¡Hola Bob!',
            body='¿Cómo estás?'
        )
    )
    print("SendMessage:", send_resp)

    # 4. Listar bandeja de Bob (server-streaming)
    print("\n== ListInbox (Bob) ==")
    for msg in stub.ListInbox(turbomessage_pb2.ListInboxRequest(token=token_bob)):
        print(f"- {msg.id}: {msg.subject} (read={msg.read})")

    # Tomamos el primer ID para leer/borrar
    first_msg = next(stub.ListInbox(turbomessage_pb2.ListInboxRequest(token=token_bob)), None)
    if first_msg:
        msg_id = first_msg.id

        # 5. Leer mensaje
        print("\n== ReadMessage ==")
        read_resp = stub.ReadMessage(
            turbomessage_pb2.ReadMessageRequest(
                token=token_bob,
                message_id=msg_id
            )
        )
        print("ReadMessage:", read_resp.message)

        # 6. Borrar mensaje
        print("\n== DeleteMessage ==")
        del_resp = stub.DeleteMessage(
            turbomessage_pb2.DeleteMessageRequest(
                token=token_bob,
                message_id=msg_id
            )
        )
        print("DeleteMessage:", del_resp)
    else:
        print("No hay mensajes en la bandeja de Bob.")

if __name__ == '__main__':
    main()
