Ustawienie klientów:
1. wejść do projektu
2. wejść do cmd
3. py -3.12 -m venv .venv (utworzenie venv)
4. .venv\Scripts\activate (aktywowanie venv)
5. pip install pygame
6. python client.py


Ustawienie serwera:
1. wsl --shutdown
2. wsl
3. hostname -I
4. odpalić powershella jako admin
5. netsh interface portproxy add v4tov4 listenport=5000 listenaddress=0.0.0.0 connectport=5000 connectaddress='adres na wsl z kroku 3'
6. wyłączenie firewall: New-NetFirewallRule -DisplayName "Czolgi Windows 10 WSL" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
