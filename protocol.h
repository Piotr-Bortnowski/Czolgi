#ifndef PROTOCOL_H
#define PROTOCOL_H

#define MAX_PLAYERS 4
#define MAX_BULLETS 20 // Maksymalnie 20 pocisków na mapie jednocześnie
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

// Struktura pojedynczego pocisku (24 bajty)
typedef struct {
    int active;
    int owner_id;
    float x, y;
    float vx, vy;
} Bullet;

// Stan gry przesyłany do wszystkich (Teraz z pociskami)
typedef struct {
    TankState tanks[MAX_PLAYERS];
    Bullet bullets[MAX_BULLETS];
} GameState;

#endif