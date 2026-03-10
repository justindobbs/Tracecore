# Autoresearch incubation

This directory is an isolated incubation lane for exploring how TraceCore could support Karpathy-style `autoresearch` workflows without changing the stable TraceCore runtime, task contracts, or specification surface.

## Purpose

This area exists to:
- prototype ideas safely
- collect notes and findings
- draft adoption-oriented narrative and article material
- validate whether `autoresearch` should become a wrapper, a task package, or a larger orchestration concept

## Boundary

Everything in this directory is experimental.

The work here must not:
- redefine core TraceCore contracts prematurely
- require spec changes before a concrete prototype proves the need
- leak `autoresearch`-specific assumptions into the stable runtime without review

## Initial structure

- `overview.md` — high-level concept and integration options
- `article-outline.md` — messaging and writing scaffold for adoption content
- `wrapper/` — future thin-wrapper prototypes
- `task/` — future TraceCore task-package prototypes
- `notes/` — research notes, findings, and experiment records

## Graduation criteria

Work should only move out of incubation if it demonstrates:
- a clear user need
- a stable enough abstraction boundary
- no avoidable coupling to existing TraceCore contracts
- a credible adoption story backed by prototypes or evidence

## Near-term direction

The preferred sequence is:
1. clarify the concept and messaging
2. prototype a thin wrapper
3. evaluate reproducibility and artifact needs
4. only then consider formal TraceCore task packaging
