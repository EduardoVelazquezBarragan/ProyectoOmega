# client.py
import grpc
import turbomessage_pb2
import turbomessage_pb2_grpc

def register(stub):
    username = input("Usuario: ")
    password = input("Contraseña: ")
    resp = stub.Register(
        turbomessage_pb2.RegisterRequest(username=username, password=password)
    )
    print("Register:", resp.message)

def login(stub):
    username = input("Usuario: ")
    password = input("Contraseña: ")
    resp = stub.Login(
        turbomessage_pb2.LoginRequest(username=username, password=password)
    )
    print("Login:", resp.message)
    return resp.token if resp.success else None

def send_message(stub, token):
    to      = input("Para (usuario): ")
    subject = input("Asunto: ")
    body    = input("Cuerpo: ")
    resp = stub.SendMessage(
        turbomessage_pb2.SendMessageRequest(
            token=token, to=to, subject=subject, body=body
        )
    )
    print("SendMessage:", resp.message)

def list_inbox(stub, token):
    print("\n== Bandeja de entrada ==")
    stream = stub.ListInbox(
        turbomessage_pb2.ListInboxRequest(token=token)
    )
    count = 0
    for msg in stream:
        count += 1
        status = "✓" if msg.read else "✗"
        print(f"{count}) {msg.id} | {msg.subject} | leído: {status}")
    if count == 0:
        print("— vacía —")

def list_outbox(stub, token):
    print("\n== Bandeja de salida ==")
    stream = stub.ListOutbox(
        turbomessage_pb2.ListOutboxRequest(token=token)
    )
    count = 0
    for msg in stream:
        count += 1
        print(f"{count}) {msg.id} | {msg.subject}")
    if count == 0:
        print("— vacía —")

def read_message(stub, token):
    msg_id = input("ID del mensaje a leer: ").strip()
    try:
        resp = stub.ReadMessage(
            turbomessage_pb2.ReadMessageRequest(
                token=token,
                message_id=msg_id
            )
        )
        m = resp.message
        print(f"\n== Mensaje {m.id} ==")
        print(f"De:     {m.sender}")
        print(f"Para:   {m.to}")
        print(f"Asunto: {m.subject}")
        print(f"Leído:  {m.read}")
        print("Cuerpo:")
        print(m.body)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            print("↳ Error: Mensaje no encontrado (ID inválido).")
        else:
            print(f"↳ Error al leer mensaje: {e.code().name} – {e.details()}")

def delete_message(stub, token):
    msg_id = input("ID del mensaje a borrar: ").strip()
    try:
        resp = stub.DeleteMessage(
            turbomessage_pb2.DeleteMessageRequest(
                token=token,
                message_id=msg_id
            )
        )
        print("DeleteMessage:", resp.message)
    except grpc.RpcError as e:
        # Manejo específico según el código de estado
        if e.code() == grpc.StatusCode.NOT_FOUND:
            print("↳ Error: Mensaje no encontrado (ID inválido).")
        else:
            print(f"↳ Error al borrar mensaje: {e.code().name} – {e.details()}")

def main():
    channel = grpc.insecure_channel('localhost:50051')
    stub    = turbomessage_pb2_grpc.TurboMessageStub(channel)
    token   = None

    menu = """
=== TurboMessage Client ===
1) Register
2) Login
3) Send Message
4) List Inbox
5) List Outbox
6) Read Message
7) Delete Message
0) Exit
"""
    try:
        while True:
            print(menu)
            choice = input("Elige una opción: ").strip()
            if choice == '1':
                register(stub)
            elif choice == '2':
                token = login(stub) or token
            elif choice == '3':
                if token: send_message(stub, token)
                else: print("↳ Necesitas hacer login primero")
            elif choice == '4':
                if token: list_inbox(stub, token)
                else: print("↳ Necesitas hacer login primero")
            elif choice == '5':
                if token: list_outbox(stub, token)
                else: print("↳ Necesitas hacer login primero")
            elif choice == '6':
                if token: read_message(stub, token)
                else: print("↳ Necesitas hacer login primero")
            elif choice == '7':
                if token: delete_message(stub, token)
                else: print("↳ Necesitas hacer login primero")
            elif choice == '0':
                print("Saliendo…")
                break
            else:
                print("Opción no válida")
    except KeyboardInterrupt:
        print("\nInterrumpido por usuario.")

if __name__ == '__main__':
    main()
