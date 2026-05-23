import socket
import struct
import pygame
import sys

# Konfiguracja
SERVER_IP = '192.168.0.74' # trzeba będzie znaleźć ip serwera
SERVER_PORT = 5000
MAX_PLAYERS = 4

# --- MAPOWANIE STRUKTUR Z JĘZYKA C ---
MAX_BULLETS = 20

# C ClientInput: (6 intów)
INPUT_FMT = '<6i' 

# Format odczytu został poszerzony o 20 pocisków
# Tank: int, int, float, float, int (iiffi)
# Bullet: int, int, float, float, float, float (iiffff)
STATE_FMT = '<' + ('iiffi' * MAX_PLAYERS) + ('iiffff' * MAX_BULLETS)
STATE_SIZE = struct.calcsize(STATE_FMT)



# Inicjalizacja Pygame
pygame.init()
screen = pygame.display.set_mode((800, 600))
pygame.display.set_caption("Rozproszone Czołgi - Klient Python")
clock = pygame.time.Clock()

# Inicjalizacja połączenia sieciowego
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.connect((SERVER_IP, SERVER_PORT))
except ConnectionRefusedError:
    print("Nie można połączyć z serwerem. Upewnij się, że serwer w C działa!")
    sys.exit()

# Serwer na powitanie wysyła nam nasze ID (jeden int = 4 bajty)
id_data = sock.recv(4)
my_id = struct.unpack('<i', id_data)[0]
print(f"Połączono! Otrzymane ID gracza: {my_id}")
print("Porusznie się: wsad/strzałki")
print("Strzał - spacja")

# Ustawienie gniazda w tryb nieblokujący (kluczowe dla płynności gry)
sock.setblocking(False)

running = True
game_state_data = None

# Definiujemy dokładnie te same ściany co na serwerze
WALLS = [
    pygame.Rect(200, 150, 50, 300),
    pygame.Rect(400, 100, 200, 50),
    pygame.Rect(500, 400, 200, 50)
]

while running:
    # 1. Obsługa zdarzeń okna
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # 2. Pobieranie stanu klawiatury
    keys = pygame.key.get_pressed()
    up    = 1 if keys[pygame.K_w] or keys[pygame.K_UP] else 0
    down  = 1 if keys[pygame.K_s] or keys[pygame.K_DOWN] else 0
    left  = 1 if keys[pygame.K_a] or keys[pygame.K_LEFT] else 0
    right = 1 if keys[pygame.K_d] or keys[pygame.K_RIGHT] else 0
    shoot = 1 if keys[pygame.K_SPACE] else 0

    # 3. Pakowanie danych do formatu C i wysyłanie
    input_data = struct.pack(INPUT_FMT, my_id, up, down, left, right, shoot)
    try:
        sock.sendall(input_data)
    except BlockingIOError:
        pass # Bufor pełny, ignorujemy w tej klatce

    # 4. Odbieranie stanu od serwera
    try:
        # Pętla opróżniająca bufor - chcemy narysować tylko najświeższy stan gry
        while True:
            chunk = sock.recv(STATE_SIZE)
            if not chunk:
                break
            if len(chunk) == STATE_SIZE:
                game_state_data = chunk
    except BlockingIOError:
        pass # Brak nowych danych do odczytu, renderujemy stary stan

    # 5. Renderowanie grafiki
    screen.fill((30, 30, 30))

    # --- RYSUJ ŚCIANY ---
    for wall in WALLS:
        pygame.draw.rect(screen, (100, 100, 100), wall)

    # --- RYSUJ CZOŁGI, HP I POCISKI ---
    if game_state_data:
        unpacked = struct.unpack(STATE_FMT, game_state_data)
        
        # 1. Rysowanie Czołgów
        for i in range(MAX_PLAYERS):
            base_idx = i * 5
            tank_id = unpacked[base_idx]
            active  = unpacked[base_idx + 1]
            x       = unpacked[base_idx + 2]
            y       = unpacked[base_idx + 3]
            hp      = unpacked[base_idx + 4]

            if active:
                color = (0, 255, 0) if tank_id == my_id else (255, 0, 0)
                rect = pygame.Rect(int(x), int(y), 40, 40)
                pygame.draw.rect(screen, color, rect)
                
                # Pasek zdrowia
                hp_ratio = hp / 100.0
                pygame.draw.rect(screen, (255, 0, 0), (int(x), int(y) - 10, 40, 5)) # Czerwone tło
                pygame.draw.rect(screen, (0, 255, 0), (int(x), int(y) - 10, int(40 * hp_ratio), 5)) # Zielone HP

        # 2. Rysowanie Pocisków
        bullet_offset = MAX_PLAYERS * 5
        for b in range(MAX_BULLETS):
            b_idx = bullet_offset + (b * 6)
            b_active = unpacked[b_idx]
            # unpacked[b_idx + 1] to owner_id, nie potrzebujemy go do rysowania
            b_x = unpacked[b_idx + 2]
            b_y = unpacked[b_idx + 3]
            
            if b_active:
                pygame.draw.rect(screen, (255, 255, 0), (int(b_x), int(b_y), 10, 10)) # Żółte pociski

    pygame.display.flip()
    clock.tick(60)

sock.close()
pygame.quit()