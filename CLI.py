import json
import requests
from sys import argv
from datetime import datetime

url = "http://lborm-469629458.us-west-2.elb.amazonaws.com/tasks/"  # url pega manualmente

COMMANDS = ["get", "add", "delete"]

if __name__ == "__main__":
    if argv[1] == COMMANDS[0]:
        print("Procurando rota /get_all...")
        response = requests.get(url + "get_all")
        print(response.text)
    elif argv[1] == COMMANDS[1]:
        if len(argv) == 4:
            print("Procurando rota /add_task...")
            title = argv[2]
            desc  = argv[3]
            date = datetime.now().isoformat()
            data = json.dumps({'title':title, 'pub_date':date, 'description': desc})
            response = requests.post(url + "add_task", data=data)
            print(response.text)
        else:
            print("Numero de argumentos incorreto.")
    elif argv[1] == COMMANDS[2]:
        print("Procurando rota /clear...")
        response = requests.delete(url + "clear")
        print(response.text)
    else:
        print("Comando invalido")
