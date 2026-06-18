# Thoughts — Alternatives to Token-Prediction as the Generative Foundation

*Research journal, June 2026. One file per thought, written so the reasoning can be re-walked later.*

## The question
Can we replace next-token autoregressive prediction as the FOUNDATION of language
GENERATION (not just trust/memory), to break the single-company model hegemony — and
do it with brain-like efficiency (cheap to train, not megawatts)?

## North star
| File | Purpose |
|---|---|
| `00_NORTH_STAR_single_company_llm_hegemony.md` | The strategic goal: beat single-company LLM hegemony by owning the learning loop |

## The 15 original research threads
| # | File | Angle |
|---|---|---|
| 01 | `01_diffusion_language_models.md` | Iterative denoising (LLaDA, MDLM, SEDD) |
| 02 | `02_jepa_energy_based.md` | Predict in latent space, not token space (LeCun) |
| 03 | `03_masked_bidirectional.md` | Fill-in-the-middle, edit-anywhere |
| 04 | `04_flow_matching.md` | Transport-based generation (rectified flow, discrete FM) |
| 05 | `05_world_models.md` | Generate by simulating/planning |
| 06 | `06_test_time_search.md` | Generation as search (o1, MCTS, tree-of-thoughts) |
| 07 | `07_process_reward_models.md` | Step-level verification steers generation |
| 08 | `08_generate_verify_reject.md` | Best-of-N, self-consistency, inference scaling |
| 09 | `09_self_supervised_beyond_prediction.md` | Contrastive, RTD, span-corruption |
| 10 | `10_program_synthesis.md` | Generate programs/derivations, render to language |
| 11 | `11_decentralized_open_ecosystems.md` | Federated training, open weights, model merging |
| 12 | `12_composable_modular.md` | MoE, adapter marketplaces, routing |
| 13 | `13_local_sovereign_ondevice.md` | Apple Intelligence, Phi, MLX, sovereign AI |
| 14 | `14_verifier_grounded_generation.md` | Generation = search + verify (AlphaGeometry) |
| 15 | `15_meta_why_prediction_won.md` | The structural forces, and what unseats them |

## The brain-efficiency threads (reduce heavy machines)
| # | File | Angle |
|---|---|---|
| 16 | `16_brain_local_learning.md` | No backprop — forward-only / local rules |
| 17 | `17_brain_predictive_coding.md` | Free Energy Principle as objective + architecture |
| 18 | `18_brain_neuromorphic_sparse.md` | Spiking, event-driven, watts not kilowatts |
| 19 | `19_brain_continual_few_shot.md` | Learn continuously, from few examples |
| 20 | `20_brain_efficiency_synthesis.md` | What a brain-out-of-the-box model would look like |

## The synthesis
| File | Purpose |
|---|---|
| `MANIFESTO_new_angle.md` | The synthesized "new angle" — one defensible bet |

## Supplemental architecture notes
| # | File | Angle |
|---|---|---|
| 21 | `21_brain_not_one_giant_model.md` | UltraBrain as cognitive architecture, not one giant model |
| 22 | `22_trust_boundary_and_verification.md` | Proposal/evidence/belief trust boundary |
| 23 | `23_beyond_token_prediction.md` | Demoting token prediction from source of truth |
| 24 | `24_self_training_loop.md` | Verified experience before weight learning |
| 25 | `25_scaling_with_less_brute_force.md` | Modular capability with less brute-force pretraining |
| 26 | `26_research_threads_summary.md` | Short summary of research paths |
| - | `README_codex_thought_log.md` | Original Codex thought-log index moved from the misplaced DUTO folder |

## One-line spine
Prediction won on *scaling laws + free labels + GPU fit*, not on theoretical optimality.
The crack: verifiers + inference-time search + brain-local learning all shift value
*away* from "one giant predictor trained on megawatts." UltraBrain's move is to own the
verifier/composition/local layer where hegemony actually breaks.
