# LLM presets (all use the same generic fields)

Copy one, add your key, and either use it as `backend/llm.env` or pass it to the evals.

```bash
cp llm-examples/openrouter-nemotron-ultra.env.example llm-examples/openrouter-nemotron-ultra.env   # gitignored
# edit: LLM_API_KEY=...
make llm-check  ENV=llm-examples/openrouter-nemotron-ultra.env   # key works? tools supported?
make llm-models ENV=llm-examples/groq.env                         # list model ids on that endpoint
make eval LLM_ENVS="llm-examples/openrouter-nemotron-ultra.env" REPEATS=1 PAUSE=8
```

| Preset | Free? | Notes |
|---|---|---|
| OpenRouter `:free` models | yes, no card | one key → many models; RPM/day limits; models rotate. Avoid `openrouter/free` for evals (random model per call) |
| Groq | yes, no card | fastest; per-model limits |
| Google AI Studio (Gemini Flash) | yes | Pro models are paid |
| Mistral Experiment | yes, no card | prompts may be used for training |
| Cerebras | yes | daily token cap, short context on free tier (our runs use ~10-20k tokens) |
