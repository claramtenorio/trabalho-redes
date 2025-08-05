import datetime

def get_current_time():
    #para pegar a data e a hora e colocar ela na mensagem
    return datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
