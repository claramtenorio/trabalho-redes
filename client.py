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
is_connected = False
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
