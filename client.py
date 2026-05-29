import socket
import struct
import pygame
import sys
import math

# Konfiguracja
SERVER_IP = '127.0.0.1' # trzeba będzie znaleźć ip serwera
SERVER_PORT = 5000
MAX_PLAYERS = 4

MAX_BULLETS = 20

# mapowanie struktur
# client input (6 * int)
INPUT_FMT = '<6i' 

# Tank: int, int, float, float, int (iiffi)
# Bullet: int, int, float, float, float, float (iiffff)
STATE_FMT = '<ii' + ('iiffi' * MAX_PLAYERS) + ('iiffff' * MAX_BULLETS)
STATE_SIZE = struct.calcsize(STATE_FMT)

pygame.init()
pygame.font.init()
ui_font = pygame.font.SysFont('Arial', 40, bold=True)
screen = pygame.display.set_mode((800, 600))
pygame.display.set_caption("Rozproszone Czołgi - Klient Python")
clock = pygame.time.Clock()

# sockety
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.connect((SERVER_IP, SERVER_PORT))
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
except ConnectionRefusedError:
    print("Nie można połączyć z serwerem. Upewnij się, że serwer w C działa!")
    sys.exit()

# odebranie id gracza
id_data = sock.recv(4)
my_id = struct.unpack('<i', id_data)[0]
print(f"Połączono! Otrzymane ID gracza: {my_id}")
print("Porusznie się: wsad/strzałki")
print("Strzał - spacja")

# ustawienie gniazda na tryb nieblokujacy
sock.setblocking(False)

running = True
game_state_data = None

# definicja ścian
WALLS = [
    pygame.Rect(200, 150, 50, 300),
    pygame.Rect(400, 100, 200, 50),
    pygame.Rect(500, 400, 200, 50)
]

# kolory graczy
PLAYER_COLORS = [
    (34, 139, 34),    # Ciemny zielony
    (30, 144, 255),   # Niebieski
    (138, 43, 226),   # Fioletowy
    (210, 105, 30)    # Pomaranczowy
]

# pamiec poprzednich pozycji i obrotow
local_player_angle = 0.0
enemy_angles = {}
prev_positions = {}

def draw_tank_with_turret(surface, x, y, angle, tank_color):
    # 1. rysowanie czolgu
    rect = pygame.Rect(int(x), int(y), 40, 40)
    pygame.draw.rect(surface, tank_color, rect)
    
    # 2. rysowanie lufy
    turret_surf = pygame.Surface((30, 8), pygame.SRCALPHA)
    color_base = (150, 150, 150)
    color_tip  = (255, 255, 0)

    pygame.draw.rect(turret_surf, color_base, (0, 0, 22, 8))
    pygame.draw.rect(turret_surf, color_tip, (22, 0, 8, 8))
    
    # 3. obrót lufy
    rotated_turret = pygame.transform.rotate(turret_surf, angle)
    
    # 4. korekcja pozycji lufy po obrocie
    turret_rect = rotated_turret.get_rect(center=(int(x) + 20, int(y) + 20))
    surface.blit(rotated_turret, turret_rect.topleft)

while running:
    # 1. obsługa eventów
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # 2. pobieranie inputów gracza
    keys = pygame.key.get_pressed()
    up    = 1 if keys[pygame.K_w] or keys[pygame.K_UP] else 0
    down  = 1 if keys[pygame.K_s] or keys[pygame.K_DOWN] else 0
    left  = 1 if keys[pygame.K_a] or keys[pygame.K_LEFT] else 0
    right = 1 if keys[pygame.K_d] or keys[pygame.K_RIGHT] else 0
    shoot = 1 if keys[pygame.K_SPACE] else 0

    # 3. wyliczanie kąta czołgu
    dx_input = right - left
    dy_input = down - up
    if dx_input != 0 or dy_input != 0:
        local_player_angle = math.degrees(math.atan2(-dy_input, dx_input)) # -dy, bo w pygame oś Y rośnie w dół

    # 4. pakowanie danych i wysłanie na serwer
    input_data = struct.pack(INPUT_FMT, my_id, up, down, left, right, shoot)
    try:
        sock.sendall(input_data)
    except BlockingIOError:
        pass

    # 5. odbieranie stanu od serwera
    try:
        while True:
            chunk = sock.recv(STATE_SIZE)
            if not chunk:
                break
            if len(chunk) == STATE_SIZE:
                game_state_data = chunk
    except BlockingIOError:
        pass 

    # 6. Renderowanie grafiki
    screen.fill((30, 30, 30))

    # 6.1 sciany
    for wall in WALLS:
        pygame.draw.rect(screen, (100, 100, 100), wall)

    # 6.2 czolgi, pociski hp
    if game_state_data:
        unpacked = struct.unpack(STATE_FMT, game_state_data)

        game_phase = unpacked[0]
        countdown = unpacked[1]

        data_offset = 2
        
        for i in range(MAX_PLAYERS):
            base_idx = data_offset + (i * 5)
            tank_id = unpacked[base_idx]
            active  = unpacked[base_idx + 1]
            x       = unpacked[base_idx + 2]
            y       = unpacked[base_idx + 3]
            hp      = unpacked[base_idx + 4]

            if active:
                color = PLAYER_COLORS[tank_id % len(PLAYER_COLORS)]
                
                if tank_id == my_id:
                    angle = local_player_angle
                else:
                    # Dla wrogów wyliczamy kierunek na podstawie ich przesunięcia od ostatniej klatki
                    prev_x, prev_y = prev_positions.get(tank_id, (x, y))
                    net_dx = x - prev_x
                    net_dy = y - prev_y
                    if net_dx != 0 or net_dy != 0:
                        enemy_angles[tank_id] = math.degrees(math.atan2(-net_dy, net_dx))
                    angle = enemy_angles.get(tank_id, 0.0)
                
                # zapis aktualnej pozycji dla nastepnej klatki
                prev_positions[tank_id] = (x, y)
                
                draw_tank_with_turret(screen, x, y, angle, color)
                
                hp_ratio = hp / 100.0
                pygame.draw.rect(screen, (255, 0, 0), (int(x), int(y) - 10, 40, 5))
                pygame.draw.rect(screen, (0, 255, 0), (int(x), int(y) - 10, int(40 * hp_ratio), 5))

        # pociski
        bullet_offset = data_offset + (MAX_PLAYERS * 5)
        for b in range(MAX_BULLETS):
            b_idx = bullet_offset + (b * 6)
            b_active = unpacked[b_idx]
            b_x = unpacked[b_idx + 2]
            b_y = unpacked[b_idx + 3]
            
            if b_active:
                pygame.draw.rect(screen, (255, 255, 0), (int(b_x), int(b_y), 10, 10))

        if game_phase == 0:
            text = ui_font.render("Oczekiwanie na graczy... (Min. 2)", True, (255, 255, 255))
            text_rect = text.get_rect(center=(400, 300))
            pygame.draw.rect(screen, (0, 0, 0), text_rect)
            screen.blit(text, text_rect)
            
        elif game_phase == 1:
            seconds_left = math.ceil(countdown / 60)
            text = ui_font.render(f"Gra startuje za: {seconds_left}", True, (255, 255, 0))
            text_rect = text.get_rect(center=(400, 300))
            pygame.draw.rect(screen, (0, 0, 0), text_rect)
            screen.blit(text, text_rect)
        
        elif game_phase == 3:
            winner_id = -1
            for i in range(MAX_PLAYERS):
                base_idx = data_offset + (i * 5)
                t_id = unpacked[base_idx]
                t_active = unpacked[base_idx + 1]
                t_hp = unpacked[base_idx + 4]
                if t_active and t_hp > 0:
                    winner_id = t_id
            
            seconds_left = math.ceil(countdown / 60)
            
            # Personalizacja komunikatu
            if winner_id == my_id:
                win_text = "Wygrałeś!"
                text_color = (0, 255, 0) # Zielony
            elif winner_id != -1:
                win_text = f"Wygrał Gracz {winner_id}!"
                text_color = PLAYER_COLORS[winner_id % len(PLAYER_COLORS)] # Kolor zwycięzcy
            else:
                win_text = "Remis! Wszyscy zginęli."
                text_color = (200, 200, 200) # Szary
                
            text1 = ui_font.render(win_text, True, text_color)
            text2 = ui_font.render(f"Nowa runda za: {seconds_left}s", True, (255, 255, 255))
            
            rect1 = text1.get_rect(center=(400, 250))
            rect2 = text2.get_rect(center=(400, 320))
            
            pygame.draw.rect(screen, (0, 0, 0), rect1.inflate(20, 20))
            pygame.draw.rect(screen, (0, 0, 0), rect2.inflate(20, 20))
            screen.blit(text1, rect1)
            screen.blit(text2, rect2)

    pygame.display.flip()
    clock.tick(60)

sock.close()
pygame.quit()