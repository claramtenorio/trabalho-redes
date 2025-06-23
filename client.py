import socket
import threading
import os
import uuid #para gerar IDs das mensagens e nomes para os arquvivos temporários que serão usados
import utils_client #importando as funcoes auxiliares do cliente
#importando constanntes que não são definidas aqui
from utils_constants import BUFFER_SIZE, HEADER_SIZE, MAX_SIZE_DATA, TYPE_HI, TYPE_BYE, TYPE_SEGMENT, TYPE_COMPLETE


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
