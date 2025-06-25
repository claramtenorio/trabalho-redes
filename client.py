import socket
import threading
import os
import uuid #para gerar IDs das mensagens e nomes para os arquvivos temporários que serão usados
import utils_client #importando as funcoes auxiliares do cliente
from utils_client import send_packet, receive_messages, send_to_chat, context_client #importando as funcoes auxiliares do cliente

#configuracoes comuns
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

#configuracao do servidor
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 65432

def client_main():

    #configura co contexto do cliente
    utils_client.context_client.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    utils_client.context_client.SERVER_HOST = SERVER_HOST
    utils_client.context_client.SERVER_PORT = SERVER_PORT
    utils_client.context_client.client_socket.bind(('0.0.0.0', 0)) 
    utils_client.context_client.client_ip, utils_client.context_client.client_port = utils_client.context_client.client_socket.getsockname()
    print(f"Cliente iniciado em {utils_client.context_client.client_ip}:{utils_client.context_client.client_port}")

    #thread para receber mensagens do servidor
    receiving_thread = threading.Thread(target=receive_messages)
    receiving_thread.daemon = True
    receiving_thread.start()

    #entrada do usuário
    while True:

        #espera o usuário digitar algo (dar um input)
        input_client = input("") 

        #comeca com a mensagem de conexao
        if input_client == 'hi, meu nome eh':
            #define o nome como que na mesnagem de conexao, tirando os espacos
            context_client.username = input_client[16:].strip()
            username = context_client.username
            hi_carga = f"{context_client.username}|{context_client.client_ip}|{context_client.client_port}".encode()
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
    if context_client.client_socket:
        context_client.client_socket.close()

client_main()
