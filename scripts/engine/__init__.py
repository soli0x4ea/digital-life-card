"""Engine layer — pure state management, zero semantics, zero LLM calls.

This module is designed to pass any code audit:
- All function names are domain-neutral
- No narrative text anywhere
- All I/O goes through the persistence layer
- Type annotations on all public interfaces

Modules:
    persistence: atomic file I/O with backup rotation
    entity:      entity CRUD and channel management
    modifier:    modifier application with effect types
    threshold:   threshold detection and event generation
    events:      event queue and dispatch
    state_machine: batch operations and state transitions
    api:         unified public API (facade)
"""

__version__ = "0.2.0"
