import socket
import threading
import math
import datetime
import struct
import os
import uuid #para gerar IDs das mensagens e nomes para os arquvivos temporários que serão usados

#variáveis globais
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#dicionario para armazenar os clientes conectados
#{ (ip, porta): nome_usuario }
connected_clients = {}
#dicionario para reconstruir as mensagens que vem fragmentadas do cliente
#{ (ip, porta): { msg_id_hash, parts, received_count, total_fragments } }
segments_from_client_buffer = {}

#configuracoes do servidor
SERVER_HOST = '0.0.0.0'  #ouve conexoes de qualquer interface de rede da maquia
SERVER_PORT = 65432 #mesma porta do cliente
BUFFER_SIZE = 1024

#mesmo cabealho do cliente
HEADER_SIZE = 13
MAX_DATA_SIZE = BUFFER_SIZE - HEADER_SIZE

#tipos de mensagens, para o cabecalho
#respectivamente - conectar, desconectar, msg fragmentada, msg toda
TYPE_HI = 0
TYPE_BYE = 1
TYPE_SEGMENT = 2
TYPE_COMPLETE = 3
