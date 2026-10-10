# Database Design — Ticket Sales API

This document describes the relational schema for the Ticket Sales API.

It is written **before** any SQLAlchemy models or Alembic migrations so that
implementation follows a reviewed design rather than the other way around.

---

## 1. Overview

The system uses three related tables:
events (1) ──── (many) seats (1) ──── (0..1) orders


- An **event** represents something for which tickets are sold.
- A **seat** belongs to exactly one event.
- An **order** exists only when a seat has been successfully reserved.

---

## 2. Tables

### 2.1 `events`

| Column       | Type                     | Constraints                     |
|--------------|--------------------------|---------------------------------|
| `id`         | `integer`                | PK, autoincrement               |
| `name`       | `varchar(255)`           | NOT NULL                        |
| `starts_at`  | `timestamptz`            | NOT NULL                        |
| `created_at` | `timestamptz`            | NOT NULL, DEFAULT `now()`       |

### 2.2 `seats`

| Column        | Type            | Constraints                                                  |
|---------------|-----------------|--------------------------------------------------------------|
| `id`          | `integer`       | PK, autoincrement                                            |
| `event_id`    | `integer`       | FK → `events.id`, NOT NULL, ON DELETE CASCADE                |
| `seat_number` | `varchar(20)`   | NOT NULL                                                     |
| `status`      | `varchar(20)`   | NOT NULL, DEFAULT `'free'`, CHECK IN (`'free'`, `'reserved'`)|
| `created_at`  | `timestamptz`   | NOT NULL, DEFAULT `now()`                                    |

Table-level constraints:

- `UNIQUE (event_id, seat_number)` — no two seats in the same event share a number.

### 2.3 `orders`

| Column       | Type          | Constraints                                          |
|--------------|---------------|------------------------------------------------------|
| `id`         | `integer`     | PK, autoincrement                                    |
| `seat_id`    | `integer`     | FK → `seats.id`, NOT NULL, UNIQUE, ON DELETE RESTRICT|
| `created_at` | `timestamptz` | NOT NULL, DEFAULT `now()`                            |

---

## 3. Relationships

| From      | To        | Cardinality | On delete     |
|-----------|-----------|-------------|---------------|
| `events`  | `seats`   | 1 → many    | CASCADE       |
| `seats`   | `orders`  | 1 → 0..1    | RESTRICT      |

---

## 4. Design Decisions and Rationale

### 4.1 `timestamptz` instead of `timestamp`

Storing timestamps without a timezone loses information and causes subtle
bugs when events happen across time zones. `timestamptz` stores an absolute
instant (UTC internally) and renders correctly for any client.

### 4.2 `seat_number` as `varchar(20)`

Real venues use section-based numbering (`A1`, `A2`, `VIP-3`, `GA-14`).
A numeric type would force us into assumptions we cannot guarantee.

### 4.3 `status` column on `seats`, not derived from `orders`

There are two valid models:

- **Derive from `orders`** — a seat is reserved iff an order exists.
- **Store `status` on `seats`** — orders act as a historical record.

We chose the stored `status` model because:

1. It enables the atomic reservation pattern used to prevent race conditions:
   `UPDATE seats SET status='reserved' WHERE id=? AND status='free'`,
   then inspecting the affected row count.
2. It makes the free-seat listing query trivially indexable
   (`WHERE event_id=? AND status='free'`).
3. It scales to richer lifecycle states (`held`, `cancelled`, `refunded`)
   without structural change.

The risk of "two sources of truth" is eliminated by performing the seat
update and the order insert inside a **single database transaction**.

### 4.4 `UNIQUE(orders.seat_id)` as a secondary defence

The primary concurrency guard is the atomic `UPDATE`. As a secondary
database-level guarantee, `orders.seat_id` is UNIQUE — the database itself
will refuse to create a second order for the same seat, even if the
application logic is ever broken by a future refactor.

### 4.5 `orders` kept minimal

An order row exists only after a reservation has succeeded. Adding an
`orders.status` column (`pending`, `paid`, `cancelled`) is deliberately
deferred — the current design reflects that "the order exists" already
means "the reservation succeeded".

### 4.6 Delete behaviour

- `events → seats` uses `CASCADE`: seats do not exist independently of
  their event.
- `seats → orders` uses `RESTRICT`: a seat with a sales record cannot be
  deleted, preserving sales history.

---

## 5. Indexes (planned)

Indexes are added deliberately in a later milestone, after measuring the
free-seat query with `EXPLAIN ANALYZE`. The candidate index is:

```sql
CREATE INDEX ... ON seats (event_id, status);