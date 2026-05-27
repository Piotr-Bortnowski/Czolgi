#ifndef PROTOCOL_H
#define PROTOCOL_H

#define MAX_PLAYERS 4
#define MAX_BULLETS 20
#define SERVER_PORT 5000
#define TICK_RATE 60

typedef struct {
    int id;
    int up, down, left, right;
    int shoot;
} ClientInput;

typedef struct {
    int id;
    int active;
    float x, y;
    int hp;
} TankState;

typedef struct {
    int active;
    int owner_id;
    float x, y;
    float vx, vy;
} Bullet;

typedef struct {
    int game_phase; // 0-czekanie; 1-odliczanie; 2-aktywna gra
    int countdown_timer; // ticki odliczane do zaczecia gry

    TankState tanks[MAX_PLAYERS];
    Bullet bullets[MAX_BULLETS];
} GameState;

#endif