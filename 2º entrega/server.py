import socket
import threading
import os
import utils_server #importando as funcoes auxiliares do cliente
from utils_server import treat_received_packets #importando a funcao que trata os pacotes recebidos

#configuracoes comuns
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

#configuracao do servidor
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 65432  

def server_main():
    print(f"[SERVER] Iniciando servidor com RDT3.0")

    #configuracao do servidor
    utils_server.context_server.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    utils_server.context_server.SERVER_HOST = SERVER_HOST
    utils_server.context_server.SERVER_PORT = SERVER_PORT
    utils_server.context_server.server_socket.bind((SERVER_HOST, SERVER_PORT))
    
    print(f"[SERVER] Servidor iniciado e escutando em {SERVER_HOST}:{SERVER_PORT}")
    print("[SERVER] Protocolo RDT 3.0 ativo - logs detalhados serão exibidos")

    try:
        while True:
            # Escuta e recebe pacotes
            datapacket, client_ad = utils_server.context_server.server_socket.recvfrom(BUFFER_SIZE)
            print(f"[SERVER] Pacote recebido de {client_ad} - tamanho: {len(datapacket)} bytes")

            # Threads para processar os pacotes recebidos de usuários diferentes
            threading.Thread(target=treat_received_packets, args=(datapacket, client_ad)).start()
            
    except KeyboardInterrupt:
        print("\n[SERVER] Encerrando servidor...")
    finally:
        utils_server.context_server.server_socket.close()
        print("[SERVER] Servidor encerrado.")

if __name__ == "__main__":
    server_main()
