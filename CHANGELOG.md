# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.1] - 2025-06-10

### Refactored
- Changed 'channel' key to '_channel' in event payload for internal metadata consistency.

## [0.9.0] - 2025-06-10

### Added
- Channel name metadata to every incoming message event payload.
- Explicit lifecycle management for channel background tasks (Telegram polling fix).
- New tests to verify channel name in event payload.

### Fixed
- Deprecated `datetime.datetime.utcnow()` calls replaced with timezone-aware `datetime.datetime.now(datetime.timezone.utc)`.

### Refactored
- `botbase/botapi.py` lifespan function to reduce complexity.

### Changed
- `pytest-asyncio` configuration in `pyproject.toml` to suppress deprecation warnings.

## [0.8.0] - 2025-06-03

### Added
- Example bot with custom JivoChat channel implementation
- Route logging at startup for better debugging
- Updated channel webhook path prefix for better routing

## [0.7.1] - 2025-06-02

### Added
- Message age filtering in Telegram channel

## [0.7.0] - 2025-06-02

### Added
- Session management to conversation tracker

## [0.6.1] - 2025-06-01

### Added
- Improved message formatting for Telegram channel

## [0.6.0] - 2025-06-01

### Added
- Telegram channel integration

## [0.5.0] - 2025-05-31

### Added
- Environment variable support in config files

## [0.4.0] - 2025-05-31

### Added
- SQLite support for conversation tracking
- Refactored conversation tracking system

## [0.3.0] - 2025-05-30

### Added
- `/restart` command to interactive mode
