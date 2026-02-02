# Product Specification Workflow

This directory contains the 2-phase workflow for transforming visual designs into deep technical specifications.

## Phase 1: Visual Translation
**Goal**: Convert UI screenshots into a baseline PRD.
**Input**: Screenshots + Context (5 P0 questions).
**Tool**: `prototype-to-prd` Skill.
**Output**: `baseline-prd.md`

## Phase 2: Deep Specification
**Goal**: Expand baseline PRD into a full technical spec with data models and error handling.
**Input**: `baseline-prd.md`
**Tool**: `spec-flow` Skill.
**Output**: `technical-spec.md`

## Usage
1. Place screenshots in `phase-1-visual/`.
2. Run the `run_phase1.sh` script (requires API keys).
3. Review `baseline-prd.md`.
4. Run `run_phase2.sh`.
