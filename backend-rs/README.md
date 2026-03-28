# Bamboo Backend (Rust)

## Prerequisites

### Install Rust

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env
```

### Verify Installation

```bash
rustc --version
cargo --version
```

## Build

```bash
cd backend-rs
cargo build --release
```

## Development

```bash
cargo run
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

## Project Structure

```
src/
├── main.rs              # Application entry point
├── lib.rs               # Library root
├── api/                 # API Layer
│   ├── routes/          # HTTP endpoints
│   ├── models/          # Request/Response DTOs
│   └── middleware/      # Auth, logging
├── domain/              # Domain Layer
│   ├── projects/        # Project domain
│   ├── build_plans/     # Build plan domain
│   ├── executions/      # Execution domain
│   ├── modules/         # Module registry domain
│   └── settings/        # System settings domain
├── infrastructure/     # Infrastructure Layer
│   ├── database/        # DB connection (sqlx)
│   ├── repositories/   # Data access
│   └── external/        # Bamboo/Jenkins clients
└── workers/            # Background workers
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/projects | List projects |
| POST | /api/v1/projects | Create project |
| GET | /api/v1/projects/{key} | Get project |
| PUT | /api/v1/projects/{key} | Update project |
| GET | /api/v1/build-plans/{plan_key}/active-definition | Get active definition |
| GET | /api/v1/build-plans/{plan_key}/prepare-context | Get prepare context |
| GET | /api/v1/build-plans/{plan_key}/executions | List executions |
| GET | /api/v1/modules | List modules |
| POST | /api/v1/modules/upload | Upload module |
| POST | /api/v1/modules/reload | Reload modules |
| GET | /api/v1/modules/load-status | Get load status |
| GET | /api/v1/settings | List settings |
| PUT | /api/v1/settings/{key} | Update setting |

## Commands

```bash
# Build
cargo build --release

# Run
cargo run

# Test
cargo test

# Lint
cargo clippy
cargo fmt
```
