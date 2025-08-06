import socket
import threading
import os
import uuid #para gerar IDs das mensagens e nomes para os arquvivos temporários que serão usados
import utils_client #importando as funcoes auxiliares do cliente
from utils_client import receive_messages, send_packet, send_to_chat, context_client

#configurações comuns
BUFFER_SIZE = 1024
# Tamanho do cabeçalho expandido para RDT 3.0
# 21 bytes = 1 byte tipo, 4 bytes hash_id, 4 bytes num_frag, 4 bytes total_frag,
#           4 bytes seq_num, 2 bytes checksum, 1 byte ack_flag, 1 byte is_ack
HEADER_SIZE = 21
# Tamanho máximo dos dados que podem ser enviados em uma mensagem
MAX_DATA_SIZE = BUFFER_SIZE - HEADER_SIZE
#tipos de mensagens, para o cabecalho
#respectivamente - conectar, desconectar, msg fragmentada, msg toda
TYPE_HI = 0
TYPE_BYE = 1
TYPE_SEGMENT = 2
TYPE_COMPLETE = 3

#adicionado
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 65432

def client_main():
    print(f"[CLIENTE] Iniciando cliente com RDT3.0")

     # Configuração do cliente
    utils_client.context_client.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    utils_client.context_client.SERVER_HOST = SERVER_HOST
    utils_client.context_client.SERVER_PORT = SERVER_PORT
    utils_client.context_client.connected = False
    
    print(f"[CLIENTE] Conectando ao servidor {SERVER_HOST}:{SERVER_PORT}")
    print("[CLIENTE] Protocolo RDT 3.0 ativo - logs detalhados serão exibidos")
    print("[CLIENTE] Para se conectar, digite: hi, meu nome eh <seu_nome>")
    print("[CLIENTE] Para sair, digite: tchau")

    # Thread para receber mensagens
    receive_thread = threading.Thread(target=receive_messages, daemon=True)
    receive_thread.start()
    
    try:
        while True:
            user_input = input()
            
            if user_input.lower().startswith("hi, meu nome eh "):
                if utils_client.context_client.connected:
                    print("[CLIENTE] Você já está conectado!")
                    continue
                    
                username = user_input[16:].strip()  # Remove "hi, meu nome eh "
                if not username:
                    print("[CLIENTE] Nome não pode estar vazio!")
                    continue
                
                # Conectar ao servidor
                print(f"[CLIENTE] Conectando como '{username}'...")
                utils_client.context_client.username = username
                
                # Envia mensagem de conexão com dados do cliente
                connect_msg = f"{username}|{SERVER_HOST}|{SERVER_PORT}"
                utils_client.send_packet(
                    connect_msg.encode(), 
                    0,  # message_hash_id
                    0,  # num_seg
                    1,  # total_seg
                    TYPE_HI
                )
                utils_client.context_client.connected = True
                print(f"[CLIENTE] Conectado como '{username}' - você pode começar a conversar!")
                
            elif user_input.lower() == "bye":
                if not utils_client.context_client.connected:
                    print("[CLIENTE] Você não está conectado!")
                    break
                    
                # Enviar mensagem de desconexão
                print("[CLIENTE] Desconectando...")
                utils_client.send_packet(
                    utils_client.context_client.username.encode(),
                    0,  # message_hash_id
                    0,  # num_seg
                    1,  # total_seg
                    TYPE_BYE
                )
                utils_client.context_client.connected = False
                break
                
            else:
                if not utils_client.context_client.connected:
                    print("[CLIENTE] Para se conectar, digite: hi, meu nome eh <seu_nome>")
                    continue
                    
                # Enviar mensagem do chat
                if user_input.strip():  # Não enviar mensagens vazias
                    print(f"[CLIENTE] Enviando mensagem...")
                    send_to_chat(user_input)
                    
    except KeyboardInterrupt:
        print("\n[CLIENTE] Encerrando cliente...")
    finally:
        if utils_client.context_client.connected:
            # Tentar enviar mensagem de desconexão
            try:
                utils_client.send_packet(
                    utils_client.context_client.username.encode(),
                    0, 0, 1, TYPE_BYE
                )
            except:
                pass
        
        utils_client.context_client.client_socket.close()
        print("[CLIENTE] Cliente encerrado.")

if __name__ == "__main__":
    client_main()