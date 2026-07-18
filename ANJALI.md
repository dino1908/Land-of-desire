# Anjali / Trio Full integration

This fork adds Anjali as a selectable female character and layers the Trio Full roleplay direction onto the simulator.

## Character

- Select `Anjali` in the female character list.
- Her model uses the game's built-in female morph system: warm medium-brown skin, oval/soft face, large dark eyes, medium-full lips, black long hair, slim-curvy frame, narrow waist, full natural chest, and rounded hips.
- The source profile is `Characters/Female/Exported/Anjali.json`.

## Roleplay + simulation

The pose menu contains an Anjali / Trio Full roleplay card. Select a pose to update the live scene direction. The steering source is `Data/anjali_roleplay.json`.

Core rule: the simulation controls Anjali and the environment but never invents Roshan's dialogue, movement, body response, gaze, thoughts, emotions, or consent.

## Runtime

This project requires UPBGE 0.36.1. It does not compile to WebGL. `scripts/start-a-game.sh` starts the native simulator and the LAN web companion/remote-access page used by this fork.
