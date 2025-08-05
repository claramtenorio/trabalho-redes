import socket
import threading
import os
import utils_server #importando as funcoes auxiliares do cliente
from utils_server import treat_received_packets #importando a funcao que trata os pacotes recebidos

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
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 65432  

def server_main():

    #configuracao do servidor
    utils_server.context_server.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    utils_server.context_server.SERVER_HOST = SERVER_HOST
    utils_server.context_server.SERVER_PORT = SERVER_PORT
    utils_server.context_server.server_socket.bind((SERVER_HOST, SERVER_PORT))

    while True:
        #escuta e recebe pacotes
        datapacket, client_ad = utils_server.context_server.server_socket.recvfrom(BUFFER_SIZE)
        #threads para processar os pacotes recebidos de usuarios diferentes
        threading.Thread(target=treat_received_packets, args=(datapacket, client_ad)).start()

server_main()
