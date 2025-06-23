import socket
import threading
import math
import datetime
import struct
import os
import uuid #para gerar IDs das mensagens e nomes para os arquvivos temporários que serão usados

#variáveis globais
client_socket = None
username = ""
connected = False
client_ip = "0.0.0.0"
client_port = 0
#dicionario para reconstruir as mensagens que vem fragmentadas do servidor
# { message_hash_id: {parts, received_count, total_fragments } }
segments_from_server_buffer = {}

#configuracoes do cliente
SERVER_HOST = '127.0.0.1' #localhost, servidor e clientes na  mesma maquina
SERVER_PORT = 65432 #porta alta, para eviter conflitos
BUFFER_SIZE = 1024

#tamanho do cabecalho
#13 bytes = 1 byte de tipo da mensagem, 4 bytes do hash do id da mensagem,
#4 bytes para o nem fragmento e 4 bytes para indicar o total de fragmento
HEADER_SIZE = 13
#tamanho maximo dos dados que podem ser enviados em uma mensagem
MAX_DATA_SIZE = BUFFER_SIZE - HEADER_SIZE

#tipos de mensagens, para o cabecalho
#respectivamente - conectar, desconectar, msg fragmentada, msg toda
TYPE_HI = 0
TYPE_BYE = 1
TYPE_SEGMENT = 2
TYPE_COMPLETE = 3

def client_main():

    #definindo
    global client_socket, username, connected, client_ip, client_port
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.bind(('0.0.0.0', 0)) 
    client_ip, client_port = client_socket.getsockname()
    print(f"novo cliente: {client_ip}:{client_port}")

    #thread para receber mensagens do servidor
    receiving_thread = threading.Thread(target=receive_messages)
    receiving_thread.daemon = True
    receiving_thread.start()

    #entrada do usuário
    while True:

        #espera o usuário digitar algo (dar um input)
        input_client = input("") 

        #comeca com a mensagem de conexao
        if input_client == 'hi, meu nome eh'
            #define o nome como que na mesnagem de conexao, tirando os espacos
            username = input_client[16:].strip()
            hi_carga = f"{username}|{client_ip}|{client_port}".encode()
            send_packet(hi_carga, 0, 0, 0, TYPE_HI)
            connected = True
            print(f"bem vindo(a) ao chat {username}!")
        
        #se o usuário digitar bye, desconecta
        elif input_client == "bye":
            send_packet(username.encode(), 0, 0, 0, TYPE_BYE)
            connected = False
            print("bye bye!")
            break

        #se o usuário digitar algo, envia a mensagem
        elif connected:
            send_to_chat(input_client)

        #se o usuário não estiver conectado, avisa
        else:
            print("antes de se conversar, é preciso se conectar com o comando 'hi, meu nome eh <nome>'")

    #close quando o loop para
    if client_socket:
        client_socket.close()

client_main()
