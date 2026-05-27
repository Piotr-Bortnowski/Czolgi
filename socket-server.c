#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <unistd.h>
#include <string.h>
#include <pthread.h>
#include "protocol.h"

typedef struct {
    int x, y, w, h;
} Wall;

#define NUM_WALLS 3
Wall map_walls[NUM_WALLS] = {
    {200, 150, 50, 300},
    {400, 100, 200, 50},
    {500, 400, 200, 50}
};

float spawn_points[MAX_PLAYERS][2] = {
    { 40.0f,  40.0f},   // lewy gorny
    {720.0f,  40.0f},   // prawy gorny
    { 40.0f, 520.0f},   // lewy dolny
    {720.0f, 520.0f}    // prawy dolny
};

// stany serwera czolgow
float tank_dir_x[MAX_PLAYERS];
float tank_dir_y[MAX_PLAYERS];
int shoot_cooldown[MAX_PLAYERS]; // licznik coodownu strzału

// stany gry
GameState game_state;
ClientInput client_inputs[MAX_PLAYERS];
int client_sockets[MAX_PLAYERS];
pthread_mutex_t state_mutex = PTHREAD_MUTEX_INITIALIZER;


// sprawdzenie czy dwa prostokaty na siebie nachodza
int check_collision(float x1, float y1, int w1, int h1, int x2, int y2, int w2, int h2) {
    return (x1 < x2 + w2 && x1 + w1 > x2 &&
            y1 < y2 + h2 && y1 + h1 > y2);
}

void init_game() {
    memset(&game_state, 0, sizeof(GameState));
    memset(client_inputs, 0, sizeof(client_inputs));
    for(int i=0; i<MAX_PLAYERS; i++) {
        client_sockets[i] = 0;
    }
}

void *connection_handler(void *arg) {
    int id = *(int*)arg;
    int sock = client_sockets[id];
    ClientInput input;
    
    // oczekiwanie na dane od klienta
    while (recv(sock, &input, sizeof(ClientInput), 0) > 0) {
        pthread_mutex_lock(&state_mutex);
        client_inputs[id] = input;
        pthread_mutex_unlock(&state_mutex);
    }
    
    // klient sie rozlaczyl
    fprintf(stderr, "Gracz %d odlaczyl sie.\n", id);
    pthread_mutex_lock(&state_mutex);
    game_state.tanks[id].active = 0;
    client_sockets[id] = 0;
    pthread_mutex_unlock(&state_mutex);
    
    close(sock);
    pthread_exit(NULL);
}

void *game_loop(void *arg) {
    float speed = 3.0f;
    float bullet_speed = 10.0f;
    int tank_size = 40;
    int bullet_size = 10;

    while(1) {
        pthread_mutex_lock(&state_mutex);
        
        // liczenie polaczonych graczy
        int active_players = 0;
        for(int i = 0; i < MAX_PLAYERS; i++) {
            if(game_state.tanks[i].active) active_players++;
        }

        
        if (game_state.game_phase == 0) {
            // czekanie na 2 graczy
            if (active_players >= 2) {
                game_state.game_phase = 1;
                game_state.countdown_timer = 60 * 5; // 5 sekund
            }
        } 
        else if (game_state.game_phase == 1) {
            // odliczanie
            if (active_players < 2) {
                // jesli ktos sie odlaczyl to wracamy do czekania
                game_state.game_phase = 0; 
            } else {
                game_state.countdown_timer--;
                if (game_state.countdown_timer <= 0) {
                    game_state.game_phase = 2;
                }
            }
        }

        if (game_state.game_phase == 2)
        {
            for(int i = 0; i < MAX_PLAYERS; i++) {
                if(game_state.tanks[i].active) {
                    
                    // kierunki patrzenia
                    float dx = 0.0f, dy = 0.0f;
                    if(client_inputs[i].up) dy -= 1.0f;
                    if(client_inputs[i].down) dy += 1.0f;
                    if(client_inputs[i].left) dx -= 1.0f;
                    if(client_inputs[i].right) dx += 1.0f;

                    
                    if (dx != 0.0f || dy != 0.0f) {
                        // normalizacja wektora strzalu po przekatnej
                        float length = sqrt(dx * dx + dy * dy);
                        tank_dir_x[i] = dx / length;
                        tank_dir_y[i] = dy / length;
                    }

                    // cooldown
                    if (shoot_cooldown[i] > 0) shoot_cooldown[i]--;

                    // strzelanie
                    if(client_inputs[i].shoot && shoot_cooldown[i] == 0) {
                        for(int b = 0; b < MAX_BULLETS; b++) {
                            if(!game_state.bullets[b].active) {
                                game_state.bullets[b].active = 1;
                                game_state.bullets[b].owner_id = i;
                                
                                // wysrodkowanie pocisku
                                game_state.bullets[b].x = game_state.tanks[i].x + (tank_size / 2) - (bullet_size / 2);
                                game_state.bullets[b].y = game_state.tanks[i].y + (tank_size / 2) - (bullet_size / 2);
                                
                                // dodanie predkosci pocisku
                                game_state.bullets[b].vx = tank_dir_x[i] * bullet_speed;
                                game_state.bullets[b].vy = tank_dir_y[i] * bullet_speed;
                                
                                // pol sekundy opoznienia miedzy strzalami
                                shoot_cooldown[i] = 30; 
                                break;
                            }
                        }
                    }

                    // ruch os x
                    float next_x = game_state.tanks[i].x;
                    if(client_inputs[i].left) next_x -= speed;
                    if(client_inputs[i].right) next_x += speed;
                    if (next_x < 0) next_x = 0;
                    if (next_x > 800 - tank_size) next_x = 800 - tank_size;

                    // kolizje os x
                    int collision_x = 0;
                    for(int w = 0; w < NUM_WALLS; w++) {
                        if(check_collision(next_x, game_state.tanks[i].y, tank_size, tank_size,
                                        map_walls[w].x, map_walls[w].y, map_walls[w].w, map_walls[w].h)) {
                            collision_x = 1; break;
                        }
                    }
                    if(!collision_x) game_state.tanks[i].x = next_x;

                    // ruch os y
                    float next_y = game_state.tanks[i].y;
                    if(client_inputs[i].up) next_y -= speed;
                    if(client_inputs[i].down) next_y += speed;
                    if (next_y < 0) next_y = 0;
                    if (next_y > 600 - tank_size) next_y = 600 - tank_size;

                    // kolizje os y
                    int collision_y = 0;
                    for(int w = 0; w < NUM_WALLS; w++) {
                        if(check_collision(game_state.tanks[i].x, next_y, tank_size, tank_size,
                                        map_walls[w].x, map_walls[w].y, map_walls[w].w, map_walls[w].h)) {
                            collision_y = 1; break;
                        }
                    }
                    if(!collision_y) game_state.tanks[i].y = next_y;
                }
            }
        }
        
        // aktualizacja pozycji pociskow
        for(int b = 0; b < MAX_BULLETS; b++) {
            if(game_state.bullets[b].active) {
                game_state.bullets[b].x += game_state.bullets[b].vx;
                game_state.bullets[b].y += game_state.bullets[b].vy;
                
                // nie nie jest poza ekranem
                if(game_state.bullets[b].x < 0 || game_state.bullets[b].x > 800 ||
                   game_state.bullets[b].y < 0 || game_state.bullets[b].y > 600) {
                    game_state.bullets[b].active = 0;
                    continue;
                }

                // kolizje pociskow ze scianami
                int hit_wall = 0;
                for(int w = 0; w < NUM_WALLS; w++) {
                    if(check_collision(game_state.bullets[b].x, game_state.bullets[b].y, bullet_size, bullet_size,
                                       map_walls[w].x, map_walls[w].y, map_walls[w].w, map_walls[w].h)) {
                        game_state.bullets[b].active = 0;
                        hit_wall = 1;
                        break;
                    }
                }
                if (hit_wall) continue;

                // kolizje z graczami
                for(int p = 0; p < MAX_PLAYERS; p++) {
                    // sprawdzenie czy trafienie aktywnego gracza innego niz ten ktory strzelil
                    if(game_state.tanks[p].active && game_state.bullets[b].owner_id != p) {
                        if(check_collision(game_state.bullets[b].x, game_state.bullets[b].y, bullet_size, bullet_size,
                                           game_state.tanks[p].x, game_state.tanks[p].y, tank_size, tank_size)) {
                            
                            game_state.bullets[b].active = 0;
                            game_state.tanks[p].hp -= 20;
                            
                            // smierc gracza
                            if(game_state.tanks[p].hp <= 0) {
                                game_state.tanks[p].active = 0;
                            }
                            break;
                        }
                    }
                }
            }
        }
        
        // wyslanie stanu gry
        for(int i = 0; i < MAX_PLAYERS; i++) {
            if(client_sockets[i] != 0) {
                send(client_sockets[i], &game_state, sizeof(GameState), MSG_NOSIGNAL);
            }
        }
        pthread_mutex_unlock(&state_mutex);
        
        usleep(1000000 / TICK_RATE);
    }
    return NULL;
}

int main(int argc, char *argv[]) {
    int listenfd, connfd;
    struct sockaddr_in serv_addr; 
    pthread_t game_thread;

    init_game();
    listenfd = socket(AF_INET, SOCK_STREAM, 0);
    int opt = 1;
    setsockopt(listenfd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    memset(&serv_addr, '0', sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr.s_addr = htonl(INADDR_ANY);
    serv_addr.sin_port = htons(SERVER_PORT); 

    bind(listenfd, (struct sockaddr*)&serv_addr, sizeof(serv_addr)); 
    listen(listenfd, MAX_PLAYERS); 
    
    fprintf(stderr, "Serwer wystartowal. Oczekiwanie na graczy...\n");
    pthread_create(&game_thread, NULL, game_loop, NULL);

    for (;;) {
        connfd = accept(listenfd, (struct sockaddr*)NULL, NULL);
        
        pthread_mutex_lock(&state_mutex);
        int assigned_id = -1;
        for(int i = 0; i < MAX_PLAYERS; i++) {
            if(client_sockets[i] == 0) {
                assigned_id = i;
                client_sockets[i] = connfd;
                game_state.tanks[i].id = i;
                game_state.tanks[i].active = 1;
                game_state.tanks[i].x = spawn_points[i][0];
                game_state.tanks[i].y = spawn_points[i][1];
                game_state.tanks[i].hp = 100;

                shoot_cooldown[i] = 0;
                tank_dir_x[i] = 0.0f;
                tank_dir_y[i] = -1.0f;
                break;
            }
        }
        pthread_mutex_unlock(&state_mutex);

        if (assigned_id != -1) {
            fprintf(stderr, "Polaczono nowego gracza! Przydzielono ID: %d\n", assigned_id);
            // Wysyłamy ID graczowi, aby wiedział kim jest
            send(connfd, &assigned_id, sizeof(int), 0); 
            
            pthread_t client_thread;
            int *id_arg = malloc(sizeof(int));
            *id_arg = assigned_id;
            pthread_create(&client_thread, NULL, connection_handler, (void *)id_arg);
        } else {
            fprintf(stderr, "Serwer pelny. Odrzucam polaczenie.\n");
            close(connfd);
        }
    }
}