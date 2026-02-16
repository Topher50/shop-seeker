# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Shop Seeker — project details to be filled in as the codebase develops.

## Commands

- **Test:** `pytest` (run from repo root with venv activated)
- **Build:** `sam build --use-container` (`--use-container` is required because `curl_cffi` has native C dependencies that must be compiled for the Lambda Linux runtime)

## Architecture

<!-- Document high-level architecture, key patterns, and important design decisions here -->
